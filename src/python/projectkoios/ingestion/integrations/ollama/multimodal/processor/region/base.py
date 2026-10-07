from __future__ import annotations

import base64
import json
import math
from typing import Any

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.integrations.ollama.base import (
    OLLAMA_BACKEND_NAME,
    OllamaHttpResponse,
    OllamaMultimodalConfigurationError,
    OllamaTransport,
    OllamaTransportError,
    OllamaTransportFailureKind,
)
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    _HARD_MAX_JSON_DEPTH,
    _HARD_MAX_JSON_INTEGER_DIGITS,
    _HARD_MAX_JSON_ITEMS,
    _HARD_MAX_JSON_STRING_BYTES,
    _HARD_MAX_MODEL_NAME_BYTES,
    _HARD_MAX_REQUEST_BYTES,
    _HARD_MAX_RESPONSE_BYTES,
    OLLAMA_REQUIRED_CAPABILITIES,
    OllamaMetadataResponseIdentity,
    OllamaMetadataStage,
    OllamaModelVerification,
    OllamaModelVerificationStatus,
    OllamaMultimodalConfiguration,
    OllamaMultimodalDeterminism,
    OllamaMultimodalFailure,
    OllamaMultimodalFailureKind,
    OllamaMultimodalLimits,
    OllamaMultimodalProposal,
    OllamaMultimodalSelectionResult,
    OllamaMultimodalWarning,
    OllamaPromptRecord,
    OllamaRawResponseIdentity,
)
from projectkoios.ingestion.integrations.ollama.transport.http import (
    LoopbackOllamaHttpTransport,
)
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer

from .identity import OllamaMultimodalRegionProcessorIdentity
from .model_list.model import OllamaModelDescriptor
from .model_list.result import OllamaModelListVerificationResult
from .preflight.result import OllamaMultimodalPreflightResult
from .request import OllamaMultimodalRegionProcessingRequest
from .result import OllamaMultimodalRegionProcessingResult


class _ResponseIssue(ValueError):
    def __init__(
        self,
        kind: OllamaMultimodalFailureKind,
        code: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.code = code
        self.message = message

    def as_failure(self) -> OllamaMultimodalFailure:
        return OllamaMultimodalFailure(
            kind=self.kind,
            code=self.code,
            message=self.message,
            retryable=False,
        )


class OllamaMultimodalRegionProcessor(
    DataObjectActionizer[
        OllamaMultimodalRegionProcessingRequest,
        OllamaMultimodalRegionProcessingResult,
    ]
):
    """Concrete bounded Ollama adapter over exact rendered PNG evidence."""

    @classmethod
    def _response_schema(cls) -> dict[str, object]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "task", "items"],
            "properties": {
                "schema_version": {"type": "integer", "const": 1},
                "task": {
                    "type": "string",
                    "const": "page_region_transcription",
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "index",
                            "selection_id",
                            "text",
                            "warnings",
                        ],
                        "properties": {
                            "index": {"type": "integer", "minimum": 0},
                            "selection_id": {"type": "string"},
                            "text": {"type": "string"},
                            "warnings": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }

    name = OllamaMultimodalRegionProcessorIdentity.PROCESSOR_NAME

    def __init__(
        self,
        *,
        configuration: OllamaMultimodalConfiguration,
        transport: OllamaTransport | None = None,
    ) -> None:
        if not isinstance(configuration, OllamaMultimodalConfiguration):
            raise TypeError(
                "configuration must be OllamaMultimodalConfiguration"
            )
        self.configuration = configuration
        self.transport = transport or LoopbackOllamaHttpTransport()
        self.version = OllamaMultimodalRegionProcessorIdentity.PROCESSOR_VERSION

    def identity(self) -> OllamaMultimodalRegionProcessorIdentity:
        """Return identity; runtime metadata is verified separately."""
        return OllamaMultimodalRegionProcessorIdentity(
            processor_name=self.name,
            processor_version=self.version,
            backend_name=OLLAMA_BACKEND_NAME,
            expected_backend_version=self.configuration.expected_ollama_version,
            endpoint=self.configuration.endpoint,
            model_name=self.configuration.model_name,
            expected_model_digest=self.configuration.expected_model_digest,
            required_capabilities=OLLAMA_REQUIRED_CAPABILITIES,
            prompt_version=OllamaPromptRecord.CONTRACT_VERSION,
            prompt_template_sha256=OllamaPromptRecord._prompt_template_sha256(),
            response_schema_version=(
                OllamaMultimodalRegionProcessorIdentity.RESPONSE_SCHEMA_VERSION
            ),
            request_options=self.configuration.options,
            configuration=self.configuration,
            configuration_digest=self.configuration.configuration_digest,
            determinism=OllamaMultimodalDeterminism.NONDETERMINISTIC,
        )

    def action(
        self, *, request: OllamaMultimodalRegionProcessingRequest
    ) -> OllamaMultimodalRegionProcessingResult:
        """Process one complete multimodal request."""
        if not isinstance(request, OllamaMultimodalRegionProcessingRequest):
            raise TypeError(
                "request must be OllamaMultimodalRegionProcessingRequest"
            )
        identity = self.identity()
        empty_metadata: tuple[OllamaMetadataResponseIdentity, ...] = ()
        failure = self._validate_current_evidence_and_limits(request)
        if failure is not None:
            return OllamaMultimodalRegionProcessingResult.failed(
                request, identity, failure, empty_metadata, None, None
            )
        try:
            preflight = self._verify_preflight()
        except OllamaTransportError as error:
            return OllamaMultimodalRegionProcessingResult.failed(
                request,
                identity,
                OllamaMultimodalFailure.from_transport(error, "metadata"),
                empty_metadata,
                None,
                None,
            )
        if preflight.failure is not None:
            return OllamaMultimodalRegionProcessingResult.failed(
                request,
                identity,
                preflight.failure,
                preflight.metadata_responses,
                None,
                None,
            )
        if preflight.observed_version is None:
            raise RuntimeError("successful preflight omitted its version")
        metadata_responses = preflight.metadata_responses

        chat_body = self._chat_body(request, self.configuration)
        if len(chat_body) > self.configuration.limits.max_request_bytes:
            return OllamaMultimodalRegionProcessingResult.failed(
                request,
                identity,
                OllamaMultimodalFailure(
                    kind=OllamaMultimodalFailureKind.INPUT_LIMIT,
                    code="ollama.chat.request_too_large",
                    message="Ollama chat request exceeds configured byte limit",
                    retryable=False,
                ),
                metadata_responses,
                None,
                None,
            )
        try:
            response = self._request(
                method="POST",
                path="/api/chat",
                body=chat_body,
                max_response_bytes=self.configuration.limits.max_response_bytes,
            )
        except OllamaTransportError as error:
            return OllamaMultimodalRegionProcessingResult.failed(
                request,
                identity,
                OllamaMultimodalFailure.from_transport(error, "chat"),
                metadata_responses,
                None,
                None,
            )
        raw_identity = OllamaRawResponseIdentity(
            http_body_sha256=OllamaPromptRecord._sha256_bytes(response.body),
            http_body_byte_length=len(response.body),
            assistant_content_sha256=None,
            assistant_content_utf8_byte_length=None,
        )
        try:
            postflight = self._verify_postflight_digest()
        except OllamaTransportError as error:
            return OllamaMultimodalRegionProcessingResult.failed(
                request,
                identity,
                OllamaMultimodalFailure.from_transport(
                    error, "postflight_metadata"
                ),
                metadata_responses,
                None,
                raw_identity,
            )
        metadata_responses += (postflight.response_identity,)
        if postflight.failure is not None:
            return OllamaMultimodalRegionProcessingResult.failed(
                request,
                identity,
                postflight.failure,
                metadata_responses,
                None,
                raw_identity,
            )
        model_verification = OllamaModelVerification(
            ollama_version=preflight.observed_version,
            model_name=self.configuration.model_name,
            expected_model_digest=self.configuration.expected_model_digest,
            preflight_observed_digest=(
                self.configuration.expected_model_digest
            ),
            postflight_observed_digest=(
                self.configuration.expected_model_digest
            ),
            advertised_capabilities=tuple(sorted(preflight.capabilities)),
            status=(
                OllamaModelVerificationStatus.EXPECTED_DIGEST_VERIFIED_BEFORE_AND_AFTER
            ),
            limitation="non_atomic_tag_to_chat_binding",
        )
        response_failure = self._validate_http_response(response, "chat")
        if response_failure is not None:
            return OllamaMultimodalRegionProcessingResult.failed(
                request,
                identity,
                response_failure,
                metadata_responses,
                model_verification,
                raw_identity,
            )
        try:
            content = self._parse_chat_envelope(
                response.body, self.configuration.model_name
            )
            content_bytes = content.encode("utf-8")
            raw_identity = OllamaRawResponseIdentity(
                http_body_sha256=raw_identity.http_body_sha256,
                http_body_byte_length=raw_identity.http_body_byte_length,
                assistant_content_sha256=OllamaPromptRecord._sha256_bytes(
                    content_bytes
                ),
                assistant_content_utf8_byte_length=len(content_bytes),
            )
            selection_results = self._parse_proposals(
                content, request, self.configuration.limits
            )
        except _ResponseIssue as error:
            return OllamaMultimodalRegionProcessingResult.failed(
                request,
                identity,
                OllamaMultimodalFailure(
                    kind=error.kind,
                    code=error.code,
                    message=error.message,
                    retryable=False,
                ),
                metadata_responses,
                model_verification,
                raw_identity,
            )
        except (
            UnicodeError,
            RecursionError,
            TypeError,
            ValueError,
            OverflowError,
        ):
            return OllamaMultimodalRegionProcessingResult.failed(
                request,
                identity,
                OllamaMultimodalFailure(
                    kind=OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                    code="ollama.output.validation_error",
                    message=(
                        "Ollama output failed bounded response validation"
                    ),
                    retryable=False,
                ),
                metadata_responses,
                model_verification,
                raw_identity,
            )
        return OllamaMultimodalRegionProcessingResult.complete(
            request,
            identity,
            metadata_responses,
            model_verification,
            raw_identity,
            selection_results,
        )

    def process(
        self, request: OllamaMultimodalRegionProcessingRequest
    ) -> OllamaMultimodalRegionProcessingResult:
        """Process one request through the canonical action path."""
        return self.action(request=request)

    def _verify_preflight(self) -> OllamaMultimodalPreflightResult:
        responses: tuple[OllamaMetadataResponseIdentity, ...] = ()
        version_response = self._request(
            method="GET",
            path="/api/version",
            body=None,
            max_response_bytes=(
                self.configuration.limits.max_metadata_response_bytes
            ),
        )
        responses += (
            OllamaMetadataResponseIdentity.from_response(
                OllamaMetadataStage.PREFLIGHT_VERSION,
                "/api/version",
                version_response,
            ),
        )
        failure = self._validate_http_response(version_response, "version")
        if failure is not None:
            return OllamaMultimodalPreflightResult(
                failure=failure,
                metadata_responses=responses,
                capabilities=frozenset(),
                observed_version=None,
            )
        try:
            version = self._parse_version(version_response.body)
        except _ResponseIssue as error:
            return OllamaMultimodalPreflightResult(
                failure=error.as_failure(),
                metadata_responses=responses,
                capabilities=frozenset(),
                observed_version=None,
            )
        if version != self.configuration.expected_ollama_version:
            return OllamaMultimodalPreflightResult(
                failure=OllamaMultimodalFailure(
                    kind=(OllamaMultimodalFailureKind.BACKEND_VERSION_MISMATCH),
                    code="ollama.version.mismatch",
                    message=(
                        "Ollama runtime version does not match configuration"
                    ),
                    retryable=False,
                ),
                metadata_responses=responses,
                capabilities=frozenset(),
                observed_version=version,
            )

        try:
            tag_result = self._verify_tags(OllamaMetadataStage.PREFLIGHT_TAGS)
        except OllamaTransportError as error:
            return OllamaMultimodalPreflightResult(
                failure=OllamaMultimodalFailure.from_transport(
                    error, "preflight_tags"
                ),
                metadata_responses=responses,
                capabilities=frozenset(),
                observed_version=version,
            )
        responses += (tag_result.response_identity,)
        if tag_result.failure is not None:
            return OllamaMultimodalPreflightResult(
                failure=tag_result.failure,
                metadata_responses=responses,
                capabilities=frozenset(),
                observed_version=version,
            )

        show_body = self._json_bytes(
            {"model": self.configuration.model_name, "verbose": False}
        )
        try:
            show = self._request(
                method="POST",
                path="/api/show",
                body=show_body,
                max_response_bytes=(
                    self.configuration.limits.max_metadata_response_bytes
                ),
            )
        except OllamaTransportError as error:
            return OllamaMultimodalPreflightResult(
                failure=OllamaMultimodalFailure.from_transport(
                    error, "preflight_show"
                ),
                metadata_responses=responses,
                capabilities=frozenset(),
                observed_version=version,
            )
        responses += (
            OllamaMetadataResponseIdentity.from_response(
                OllamaMetadataStage.PREFLIGHT_SHOW, "/api/show", show
            ),
        )
        failure = self._validate_http_response(show, "model details")
        if failure is not None:
            return OllamaMultimodalPreflightResult(
                failure=failure,
                metadata_responses=responses,
                capabilities=frozenset(),
                observed_version=version,
            )
        try:
            capabilities = self._parse_capabilities(show.body)
        except _ResponseIssue as error:
            return OllamaMultimodalPreflightResult(
                failure=error.as_failure(),
                metadata_responses=responses,
                capabilities=frozenset(),
                observed_version=version,
            )
        if not set(OLLAMA_REQUIRED_CAPABILITIES).issubset(capabilities):
            failure = OllamaMultimodalFailure(
                kind=OllamaMultimodalFailureKind.MODEL_CAPABILITY_MISMATCH,
                code="ollama.model.vision_capability_missing",
                message="configured Ollama model does not advertise vision",
                retryable=False,
            )
            return OllamaMultimodalPreflightResult(
                failure=failure,
                metadata_responses=responses,
                capabilities=capabilities,
                observed_version=version,
            )
        return OllamaMultimodalPreflightResult(
            failure=None,
            metadata_responses=responses,
            capabilities=capabilities,
            observed_version=version,
        )

    def _verify_postflight_digest(
        self,
    ) -> OllamaModelListVerificationResult:
        return self._verify_tags(OllamaMetadataStage.POSTFLIGHT_TAGS)

    def _verify_tags(
        self, stage: OllamaMetadataStage
    ) -> OllamaModelListVerificationResult:
        tags = self._request(
            method="GET",
            path="/api/tags",
            body=None,
            max_response_bytes=(
                self.configuration.limits.max_metadata_response_bytes
            ),
        )
        response_identity = OllamaMetadataResponseIdentity.from_response(
            stage, "/api/tags", tags
        )
        failure = self._validate_http_response(tags, "model list")
        if failure is not None:
            return OllamaModelListVerificationResult(
                failure=failure,
                response_identity=response_identity,
            )
        try:
            models = self._parse_tags(tags.body)
        except _ResponseIssue as error:
            return OllamaModelListVerificationResult(
                failure=error.as_failure(),
                response_identity=response_identity,
            )
        matches = [
            model.model_digest
            for model in models
            if model.model_name == self.configuration.model_name
        ]
        if not matches:
            failure = OllamaMultimodalFailure(
                kind=OllamaMultimodalFailureKind.MODEL_MISSING,
                code="ollama.model.missing",
                message="explicitly configured Ollama model is not installed",
                retryable=False,
            )
        elif len(matches) != 1:
            failure = OllamaMultimodalFailure(
                kind=OllamaMultimodalFailureKind.PROTOCOL_ERROR,
                code="ollama.model.duplicate_metadata",
                message=(
                    "Ollama model list contains duplicate exact model names"
                ),
                retryable=False,
            )
        elif matches[0] != self.configuration.expected_model_digest:
            failure = OllamaMultimodalFailure(
                kind=OllamaMultimodalFailureKind.MODEL_DIGEST_MISMATCH,
                code="ollama.model.digest_mismatch",
                message=(
                    "installed Ollama model digest does not match configuration"
                ),
                retryable=False,
            )
        else:
            failure = None
        return OllamaModelListVerificationResult(
            failure=failure,
            response_identity=response_identity,
        )

    @staticmethod
    def _json_bytes(value: object) -> bytes:
        return CanonicalJsonSerializer.serialize_text(value).encode("utf-8")

    @staticmethod
    def _chat_body(
        request: OllamaMultimodalRegionProcessingRequest,
        configuration: OllamaMultimodalConfiguration,
    ) -> bytes:
        return OllamaMultimodalRegionProcessor._json_bytes(
            {
                "model": configuration.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": request.prompt.text,
                        "images": [
                            base64.b64encode(
                                item.rendered_region.content
                            ).decode("ascii")
                            for item in request.selections
                        ],
                    }
                ],
                "format": OllamaMultimodalRegionProcessor._response_schema(),
                "options": configuration.options.as_ollama_json(),
                "stream": False,
                "think": False,
                "keep_alive": configuration.options.keep_alive,
            }
        )

    @staticmethod
    def _strict_json_object(
        payload: bytes | str, context: str
    ) -> dict[str, Any]:
        def issue(code: str, message: str) -> _ResponseIssue:
            return _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                f"ollama.{context}.{code}",
                f"Ollama {context} {message}",
            )

        def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise issue(
                        "duplicate_field", "contains a duplicate JSON field"
                    )
                result[key] = value
            return result

        def parse_constant(value: str) -> object:
            raise issue(
                "non_rfc_constant",
                f"contains forbidden JSON constant {value}",
            )

        def parse_integer(value: str) -> int:
            if len(value.lstrip("-")) > _HARD_MAX_JSON_INTEGER_DIGITS:
                raise issue("integer_limit", "contains an oversized integer")
            return int(value)

        def parse_float(value: str) -> float:
            if len(value) > _HARD_MAX_JSON_INTEGER_DIGITS:
                raise issue("number_limit", "contains an oversized number")
            parsed = float(value)
            if not math.isfinite(parsed):
                raise issue("non_finite_number", "contains a non-finite number")
            return parsed

        try:
            if isinstance(payload, bytes):
                text = payload.decode("utf-8", errors="strict")
            elif isinstance(payload, str):
                payload.encode("utf-8", errors="strict")
                text = payload
            else:
                raise TypeError("JSON payload must be bytes or text")
            OllamaMultimodalRegionProcessor._validate_json_lexical_bounds(
                text, context
            )
            value = json.loads(
                text,
                object_pairs_hook=object_pairs,
                parse_constant=parse_constant,
                parse_int=parse_integer,
                parse_float=parse_float,
            )
            OllamaMultimodalRegionProcessor._validate_json_tree(value, context)
        except _ResponseIssue:
            raise
        except (
            UnicodeError,
            json.JSONDecodeError,
            RecursionError,
            TypeError,
            ValueError,
            OverflowError,
        ) as error:
            raise issue(
                "invalid_json", "is not valid bounded UTF-8 JSON"
            ) from error
        if not isinstance(value, dict):
            raise issue("not_object", "must be a JSON object")
        return value

    @staticmethod
    def _validate_json_lexical_bounds(text: str, context: str) -> None:
        depth = 0
        in_string = False
        escaped = False
        for character in text:
            if in_string:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_string = False
                continue
            if character == '"':
                in_string = True
            elif character in "[{":
                depth += 1
                if depth > _HARD_MAX_JSON_DEPTH:
                    raise _ResponseIssue(
                        OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                        f"ollama.{context}.depth_limit",
                        f"Ollama {context} exceeds the JSON depth limit",
                    )
            elif character in "]}":
                depth -= 1
                if depth < 0:
                    raise _ResponseIssue(
                        OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                        f"ollama.{context}.unbalanced_json",
                        f"Ollama {context} has unbalanced JSON containers",
                    )
        if depth != 0:
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                f"ollama.{context}.unbalanced_json",
                f"Ollama {context} has unbalanced JSON containers",
            )

    @staticmethod
    def _validate_json_tree(value: object, context: str) -> None:
        stack: list[tuple[object, int]] = [(value, 1)]
        item_count = 0
        total_string_bytes = 0
        while stack:
            item, depth = stack.pop()
            item_count += 1
            if item_count > _HARD_MAX_JSON_ITEMS:
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                    f"ollama.{context}.item_limit",
                    f"Ollama {context} exceeds the JSON item limit",
                )
            if depth > _HARD_MAX_JSON_DEPTH:
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                    f"ollama.{context}.depth_limit",
                    f"Ollama {context} exceeds the JSON depth limit",
                )
            if isinstance(item, str):
                total_string_bytes += (
                    OllamaMultimodalRegionProcessor._validate_untrusted_text(
                        context=context,
                        value=item,
                        maximum=_HARD_MAX_JSON_STRING_BYTES,
                        allow_line_controls=True,
                    )
                )
                if total_string_bytes > _HARD_MAX_RESPONSE_BYTES:
                    raise _ResponseIssue(
                        OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                        f"ollama.{context}.text_limit",
                        f"Ollama {context} exceeds the JSON text limit",
                    )
            elif isinstance(item, dict):
                for key, child in item.items():
                    stack.append((key, depth + 1))
                    stack.append((child, depth + 1))
            elif isinstance(item, list):
                stack.extend((child, depth + 1) for child in item)
            elif item is None or type(item) in (bool, int, float):
                if isinstance(item, float) and not math.isfinite(item):
                    raise _ResponseIssue(
                        OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                        f"ollama.{context}.non_finite_number",
                        f"Ollama {context} contains a non-finite number",
                    )
            else:
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                    f"ollama.{context}.unsupported_value",
                    f"Ollama {context} contains an unsupported JSON value",
                )

    @staticmethod
    def _validate_untrusted_text(
        *,
        context: str,
        value: str,
        maximum: int,
        allow_line_controls: bool,
    ) -> int:
        try:
            encoded = value.encode("utf-8", errors="strict")
        except UnicodeError as error:
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                f"ollama.{context}.invalid_unicode",
                f"Ollama {context} contains invalid Unicode",
            ) from error
        if len(encoded) > maximum:
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.OUTPUT_LIMIT,
                f"ollama.{context}.text_bytes",
                f"Ollama {context} text exceeds its byte limit",
            )
        allowed = {"\t", "\n", "\r"} if allow_line_controls else set()
        if any(
            (
                (ord(character) < 32 and character not in allowed)
                or 127 <= ord(character) <= 159
            )
            for character in value
        ):
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                f"ollama.{context}.control_character",
                f"Ollama {context} contains a forbidden control character",
            )
        return len(encoded)

    @staticmethod
    def _validate_http_response(
        response: OllamaHttpResponse, context: str
    ) -> OllamaMultimodalFailure | None:
        if response.status_code != 200:
            return OllamaMultimodalFailure(
                kind=OllamaMultimodalFailureKind.HTTP_ERROR,
                code=f"ollama.{context.replace(' ', '_')}.http_error",
                message=f"Ollama {context} request did not return HTTP 200",
                retryable=response.status_code >= 500,
            )
        media_type = response.content_type.partition(";")[0].strip().lower()
        if media_type != "application/json":
            return OllamaMultimodalFailure(
                kind=OllamaMultimodalFailureKind.PROTOCOL_ERROR,
                code=f"ollama.{context.replace(' ', '_')}.content_type",
                message=f"Ollama {context} response is not application/json",
                retryable=False,
            )
        return None

    @staticmethod
    def _parse_version(payload: bytes) -> str:
        root = OllamaMultimodalRegionProcessor._strict_json_object(
            payload, "version"
        )
        if set(root) != {"version"} or not isinstance(root["version"], str):
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                "ollama.version.shape",
                "Ollama version response has an unsupported shape",
            )
        OllamaMultimodalRegionProcessor._validate_untrusted_text(
            context="version",
            value=root["version"],
            maximum=128,
            allow_line_controls=False,
        )
        try:
            OllamaMultimodalConfiguration._validate_version(root["version"])
        except OllamaMultimodalConfigurationError as error:
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                "ollama.version.value",
                "Ollama version response has an invalid version value",
            ) from error
        return root["version"]

    @staticmethod
    def _parse_tags(payload: bytes) -> tuple[OllamaModelDescriptor, ...]:
        root = OllamaMultimodalRegionProcessor._strict_json_object(
            payload, "model_list"
        )
        if set(root) != {"models"} or not isinstance(root["models"], list):
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                "ollama.model_list.shape",
                "Ollama model list has an unsupported shape",
            )
        result: list[OllamaModelDescriptor] = []
        for item in root["models"]:
            if not isinstance(item, dict):
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                    "ollama.model_list.item",
                    "Ollama model list contains a non-object item",
                )
            name = item.get("name")
            model = item.get("model")
            digest = item.get("digest")
            if (
                not isinstance(name, str)
                or not isinstance(model, str)
                or name != model
                or not isinstance(digest, str)
            ):
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                    "ollama.model_list.identity",
                    "Ollama model metadata lacks an exact name and digest",
                )
            OllamaMultimodalRegionProcessor._validate_untrusted_text(
                context="model_list_name",
                value=name,
                maximum=_HARD_MAX_MODEL_NAME_BYTES,
                allow_line_controls=False,
            )
            OllamaMultimodalRegionProcessor._validate_untrusted_text(
                context="model_list_digest",
                value=digest,
                maximum=71,
                allow_line_controls=False,
            )
            try:
                validated_digest = (
                    OllamaMultimodalConfiguration._validate_model_digest(digest)
                )
            except OllamaMultimodalConfigurationError as error:
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                    "ollama.model_list.digest",
                    "Ollama model metadata contains an invalid digest",
                ) from error
            try:
                result.append(
                    OllamaModelDescriptor(
                        model_name=name,
                        model_digest=validated_digest,
                    )
                )
            except (OllamaMultimodalConfigurationError, ValueError) as error:
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                    "ollama.model_list.identity",
                    "Ollama model metadata contains an invalid identity",
                ) from error
        return tuple(result)

    @staticmethod
    def _parse_capabilities(payload: bytes) -> frozenset[str]:
        root = OllamaMultimodalRegionProcessor._strict_json_object(
            payload, "model_details"
        )
        capabilities = root.get("capabilities")
        if not isinstance(capabilities, list) or any(
            not isinstance(item, str) or not item for item in capabilities
        ):
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                "ollama.model_details.capabilities",
                "Ollama model details lack a valid capabilities list",
            )
        for capability in capabilities:
            OllamaMultimodalRegionProcessor._validate_untrusted_text(
                context="model_capability",
                value=capability,
                maximum=256,
                allow_line_controls=False,
            )
        if len(set(capabilities)) != len(capabilities):
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                "ollama.model_details.duplicate_capability",
                "Ollama model capabilities contain duplicates",
            )
        return frozenset(capabilities)

    @staticmethod
    def _parse_chat_envelope(payload: bytes, expected_model: str) -> str:
        root = OllamaMultimodalRegionProcessor._strict_json_object(
            payload, "chat_response"
        )
        required = {"model", "created_at", "message", "done", "done_reason"}
        allowed = required | {
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_cached_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
        }
        if not required.issubset(root) or not set(root).issubset(allowed):
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                "ollama.chat_response.fields",
                "Ollama chat response has missing or extra fields",
            )
        if root["model"] != expected_model:
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.PROTOCOL_ERROR,
                "ollama.chat_response.model_mismatch",
                "Ollama chat response names a different model",
            )
        if not isinstance(root["created_at"], str) or not root["created_at"]:
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                "ollama.chat_response.created_at",
                "Ollama chat response has an invalid timestamp",
            )
        OllamaMultimodalRegionProcessor._validate_untrusted_text(
            context="chat_created_at",
            value=root["created_at"],
            maximum=256,
            allow_line_controls=False,
        )
        if root["done"] is not True or root["done_reason"] != "stop":
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.PROTOCOL_ERROR,
                "ollama.chat_response.incomplete",
                "Ollama chat response did not finish with stop",
            )
        for key in allowed - required:
            if key in root and (
                isinstance(root[key], bool)
                or not isinstance(root[key], int)
                or root[key] < 0
            ):
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                    "ollama.chat_response.metric",
                    "Ollama chat response contains an invalid metric",
                )
        message = root["message"]
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                "ollama.chat_response.message",
                "Ollama chat response message has an unsupported shape",
            )
        if message["role"] != "assistant" or not isinstance(
            message["content"], str
        ):
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                "ollama.chat_response.message_content",
                "Ollama chat response lacks assistant text content",
            )
        return message["content"]

    @staticmethod
    def _parse_proposals(
        content: str,
        request: OllamaMultimodalRegionProcessingRequest,
        limits: OllamaMultimodalLimits,
    ) -> tuple[OllamaMultimodalSelectionResult, ...]:
        content_byte_length = (
            OllamaMultimodalRegionProcessor._validate_untrusted_text(
                context="structured_output",
                value=content,
                maximum=limits.max_output_bytes,
                allow_line_controls=True,
            )
        )
        if content_byte_length > limits.max_output_bytes:
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.OUTPUT_LIMIT,
                "ollama.output.total_bytes",
                "Ollama structured output exceeds configured byte limit",
            )
        root = OllamaMultimodalRegionProcessor._strict_json_object(
            content, "structured_output"
        )
        if set(root) != {"schema_version", "task", "items"}:
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                "ollama.output.fields",
                "Ollama structured output has missing or extra fields",
            )
        if (
            type(root["schema_version"]) is not int
            or root["schema_version"]
            != OllamaMultimodalRegionProcessorIdentity.RESPONSE_SCHEMA_VERSION
        ):
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                "ollama.output.schema_version",
                "Ollama structured output uses an unsupported schema",
            )
        if root["task"] != request.task_kind.value:
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                "ollama.output.task",
                "Ollama structured output names a different task",
            )
        items = root["items"]
        if not isinstance(items, list) or len(items) != len(request.selections):
            raise _ResponseIssue(
                OllamaMultimodalFailureKind.INCOMPLETE_COVERAGE,
                "ollama.output.coverage_count",
                "Ollama output does not cover every selected image",
            )
        results: list[OllamaMultimodalSelectionResult] = []
        total_text_bytes = 0
        for index, (item, selection) in enumerate(
            zip(items, request.selections, strict=True)
        ):
            if not isinstance(item, dict) or set(item) != {
                "index",
                "selection_id",
                "text",
                "warnings",
            }:
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                    "ollama.output.item_fields",
                    "Ollama output item has missing or extra fields",
                )
            if type(item["index"]) is not int:
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                    "ollama.output.item_index_type",
                    "Ollama output item index must be an integer",
                )
            if (
                item["index"] != index
                or item["selection_id"] != selection.selection_id
            ):
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.INCOMPLETE_COVERAGE,
                    "ollama.output.order_or_identity",
                    "Ollama output order or selection identity is incomplete",
                )
            text = item["text"]
            warnings = item["warnings"]
            if not isinstance(text, str) or not isinstance(warnings, list):
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                    "ollama.output.item_types",
                    "Ollama output item has invalid value types",
                )
            text_byte_length = (
                OllamaMultimodalRegionProcessor._validate_untrusted_text(
                    context="proposal_text",
                    value=text,
                    maximum=limits.max_output_bytes_per_selection,
                    allow_line_controls=True,
                )
            )
            text_bytes = text.encode("utf-8")
            total_text_bytes += text_byte_length
            if len(text_bytes) > limits.max_output_bytes_per_selection:
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.OUTPUT_LIMIT,
                    "ollama.output.selection_bytes",
                    "Ollama selection text exceeds configured byte limit",
                )
            if total_text_bytes > limits.max_output_bytes:
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.OUTPUT_LIMIT,
                    "ollama.output.text_bytes",
                    "Ollama proposal text exceeds configured byte limit",
                )
            if len(warnings) > limits.max_warnings_per_selection:
                raise _ResponseIssue(
                    OllamaMultimodalFailureKind.OUTPUT_LIMIT,
                    "ollama.output.warning_count",
                    "Ollama output contains too many warnings",
                )
            parsed_warnings: list[OllamaMultimodalWarning] = []
            for warning_index, warning in enumerate(warnings):
                if not isinstance(warning, str) or not warning:
                    raise _ResponseIssue(
                        OllamaMultimodalFailureKind.MALFORMED_RESPONSE,
                        "ollama.output.warning_type",
                        "Ollama output warning must be a nonempty string",
                    )
                warning_byte_length = (
                    OllamaMultimodalRegionProcessor._validate_untrusted_text(
                        context="proposal_warning",
                        value=warning,
                        maximum=limits.max_warning_bytes,
                        allow_line_controls=False,
                    )
                )
                if warning_byte_length > limits.max_warning_bytes:
                    raise _ResponseIssue(
                        OllamaMultimodalFailureKind.OUTPUT_LIMIT,
                        "ollama.output.warning_bytes",
                        "Ollama output warning exceeds configured byte limit",
                    )
                parsed_warnings.append(
                    OllamaMultimodalWarning(
                        code=f"ollama.model.warning.{warning_index}",
                        message=warning,
                    )
                )
            proposal = OllamaMultimodalProposal(
                text=text,
                text_sha256=OllamaPromptRecord._sha256_bytes(text_bytes),
                text_utf8_byte_length=len(text_bytes),
                warnings=tuple(parsed_warnings),
            )
            results.append(
                OllamaMultimodalSelectionResult.from_selection(
                    selection, proposal=proposal, failure=None
                )
            )
        return tuple(results)

    def _request(
        self,
        *,
        method: str,
        path: str,
        body: bytes | None,
        max_response_bytes: int,
    ) -> OllamaHttpResponse:
        if body is not None and len(body) > _HARD_MAX_REQUEST_BYTES:
            raise OllamaTransportError(
                OllamaTransportFailureKind.PROTOCOL,
                "Ollama request exceeds implementation byte limit",
            )
        response = self.transport.request(
            endpoint=self.configuration.endpoint,
            method=method,
            path=path,
            body=body,
            connect_timeout_seconds=float(
                self.configuration.connect_timeout_seconds
            ),
            read_timeout_seconds=float(self.configuration.read_timeout_seconds),
            max_response_bytes=max_response_bytes,
        )
        if not isinstance(response, OllamaHttpResponse):
            raise OllamaTransportError(
                OllamaTransportFailureKind.PROTOCOL,
                "Ollama transport returned an invalid response type",
            )
        if len(response.body) > max_response_bytes:
            raise OllamaTransportError(
                OllamaTransportFailureKind.RESPONSE_LIMIT,
                "Ollama transport returned an oversized response",
            )
        return response

    def _validate_current_evidence_and_limits(
        self, request: OllamaMultimodalRegionProcessingRequest
    ) -> OllamaMultimodalFailure | None:
        limits = self.configuration.limits
        if len(request.selections) > limits.max_selections:
            return OllamaMultimodalFailure.input_limit("selection_count")
        total_bytes = 0
        total_pixels = 0
        for selection in request.selections:
            region = selection.rendered_region
            if (
                OllamaPromptRecord._sha256_bytes(region.content)
                != selection.png_sha256
                or len(region.content) != selection.png_byte_length
                or region.content_sha256 != selection.png_sha256
                or region.byte_length != selection.png_byte_length
                or region.region_id != selection.region_id
                or region.source_id != selection.source_id
                or region.source_blob_id != selection.source_blob_id
                or region.source_content_hash != selection.source_content_hash
                or region.page_index != selection.page_index
                or region.width_pixels != selection.width_pixels
                or region.height_pixels != selection.height_pixels
            ):
                return OllamaMultimodalFailure(
                    kind=OllamaMultimodalFailureKind.STALE_EVIDENCE,
                    code="ollama.input.stale_rendered_region",
                    message="rendered PNG evidence no longer matches selection",
                    retryable=False,
                )
            pixels = selection.width_pixels * selection.height_pixels
            if selection.png_byte_length > limits.max_image_bytes:
                return OllamaMultimodalFailure.input_limit("image_bytes")
            if pixels > limits.max_pixels_per_image:
                return OllamaMultimodalFailure.input_limit("image_pixels")
            total_bytes += selection.png_byte_length
            total_pixels += pixels
        if total_bytes > limits.max_total_image_bytes:
            return OllamaMultimodalFailure.input_limit("total_image_bytes")
        if total_pixels > limits.max_total_pixels:
            return OllamaMultimodalFailure.input_limit("total_image_pixels")
        if request.prompt.utf8_byte_length > limits.max_prompt_bytes:
            return OllamaMultimodalFailure.input_limit("prompt_bytes")
        return None

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import canonical_json, stable_id
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMetadataResponseIdentity,
    OllamaMetadataStage,
    OllamaModelVerification,
    OllamaMultimodalDeterminism,
    OllamaMultimodalEvidenceStatus,
    OllamaMultimodalFailure,
    OllamaMultimodalResultStatus,
    OllamaMultimodalSelectionResult,
    OllamaMultimodalSelectionStatus,
    OllamaMultimodalTaskKind,
    OllamaPromptRecord,
    OllamaRawResponseIdentity,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash

from .identity import OllamaMultimodalRegionProcessorIdentity
from .request import OllamaMultimodalRegionProcessingRequest


@dataclass(frozen=True)
class OllamaMultimodalRegionProcessingResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    CONTRACT_NAME: ClassVar[str] = "ollama-multimodal-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    contract_version: str
    request_id: str
    processor_identity: OllamaMultimodalRegionProcessorIdentity
    task_kind: OllamaMultimodalTaskKind
    prompt: OllamaPromptRecord
    status: OllamaMultimodalResultStatus
    evidence_status: OllamaMultimodalEvidenceStatus
    determinism: OllamaMultimodalDeterminism
    cacheable: bool
    metadata_responses: tuple[OllamaMetadataResponseIdentity, ...]
    model_verification: OllamaModelVerification | None
    raw_response: OllamaRawResponseIdentity | None
    selection_results: tuple[OllamaMultimodalSelectionResult, ...]

    @classmethod
    def failed(
        cls,
        request: OllamaMultimodalRegionProcessingRequest,
        processor_identity: OllamaMultimodalRegionProcessorIdentity,
        failure: OllamaMultimodalFailure,
        metadata_responses: tuple[OllamaMetadataResponseIdentity, ...],
        model_verification: OllamaModelVerification | None,
        raw_response: OllamaRawResponseIdentity | None,
    ) -> OllamaMultimodalRegionProcessingResult:
        selection_results = tuple(
            OllamaMultimodalSelectionResult.from_selection(
                selection,
                proposal=None,
                failure=failure,
            )
            for selection in request.selections
        )
        return cls._create(
            request=request,
            processor_identity=processor_identity,
            status=OllamaMultimodalResultStatus.FAILED,
            cacheable=False,
            metadata_responses=metadata_responses,
            model_verification=model_verification,
            raw_response=raw_response,
            selection_results=selection_results,
        )

    @classmethod
    def complete(
        cls,
        request: OllamaMultimodalRegionProcessingRequest,
        processor_identity: OllamaMultimodalRegionProcessorIdentity,
        metadata_responses: tuple[OllamaMetadataResponseIdentity, ...],
        model_verification: OllamaModelVerification,
        raw_response: OllamaRawResponseIdentity,
        selection_results: tuple[OllamaMultimodalSelectionResult, ...],
    ) -> OllamaMultimodalRegionProcessingResult:
        return cls._create(
            request=request,
            processor_identity=processor_identity,
            status=OllamaMultimodalResultStatus.COMPLETE,
            cacheable=True,
            metadata_responses=metadata_responses,
            model_verification=model_verification,
            raw_response=raw_response,
            selection_results=selection_results,
        )

    @classmethod
    def _create(
        cls,
        *,
        request: OllamaMultimodalRegionProcessingRequest,
        processor_identity: OllamaMultimodalRegionProcessorIdentity,
        status: OllamaMultimodalResultStatus,
        cacheable: bool,
        metadata_responses: tuple[OllamaMetadataResponseIdentity, ...],
        model_verification: OllamaModelVerification | None,
        raw_response: OllamaRawResponseIdentity | None,
        selection_results: tuple[OllamaMultimodalSelectionResult, ...],
    ) -> OllamaMultimodalRegionProcessingResult:
        evidence_status = OllamaMultimodalEvidenceStatus.AUTOMATED_UNREVIEWED
        determinism = OllamaMultimodalDeterminism.NONDETERMINISTIC
        result_id = cls._result_id(
            request_id=request.request_id,
            processor_identity=processor_identity,
            task_kind=request.task_kind,
            prompt=request.prompt,
            status=status,
            evidence_status=evidence_status,
            determinism=determinism,
            cacheable=cacheable,
            metadata_responses=metadata_responses,
            model_verification=model_verification,
            raw_response=raw_response,
            selection_results=selection_results,
        )
        return cls(
            result_id=result_id,
            contract_version=cls.CONTRACT_VERSION,
            request_id=request.request_id,
            processor_identity=processor_identity,
            task_kind=request.task_kind,
            prompt=request.prompt,
            status=status,
            evidence_status=evidence_status,
            determinism=determinism,
            cacheable=cacheable,
            metadata_responses=metadata_responses,
            model_verification=model_verification,
            raw_response=raw_response,
            selection_results=selection_results,
        )

    @classmethod
    def _result_id(
        cls,
        *,
        request_id: str,
        processor_identity: OllamaMultimodalRegionProcessorIdentity,
        task_kind: OllamaMultimodalTaskKind,
        prompt: OllamaPromptRecord,
        status: OllamaMultimodalResultStatus,
        evidence_status: OllamaMultimodalEvidenceStatus,
        determinism: OllamaMultimodalDeterminism,
        cacheable: bool,
        metadata_responses: tuple[OllamaMetadataResponseIdentity, ...],
        model_verification: OllamaModelVerification | None,
        raw_response: OllamaRawResponseIdentity | None,
        selection_results: tuple[OllamaMultimodalSelectionResult, ...],
    ) -> str:
        return stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            request_id,
            processor_identity,
            task_kind,
            prompt,
            status,
            evidence_status,
            determinism,
            cacheable,
            metadata_responses,
            model_verification,
            raw_response,
            selection_results,
        )

    @staticmethod
    def _validate_prompt_coverage(
        prompt: OllamaPromptRecord,
        results: tuple[OllamaMultimodalSelectionResult, ...],
    ) -> None:
        marker = "Ordered evidence manifest:\n"
        if prompt.text.count(marker) != 1 or not prompt.text.endswith("\n"):
            raise ValueError("prompt does not contain one canonical manifest")
        manifest_text = prompt.text.split(marker, 1)[1][:-1]
        try:
            manifest = json.loads(manifest_text)
        except json.JSONDecodeError as error:
            raise ValueError("prompt evidence manifest is invalid") from error
        expected = [
            {
                "index": index,
                "selection_id": item.selection_id,
                "source_id": item.source_id,
                "source_blob_id": item.source_blob_id,
                "source_content_hash": item.source_content_hash,
                "page_index": item.page_index,
                "region_id": item.region_id,
                "png_sha256": item.png_sha256,
                "png_byte_length": item.png_byte_length,
                "width_pixels": item.width_pixels,
                "height_pixels": item.height_pixels,
            }
            for index, item in enumerate(results)
        ]
        if manifest != expected or manifest_text != canonical_json(expected):
            raise ValueError(
                "result coverage does not match prompt evidence manifest"
            )

    def __post_init__(self) -> None:
        self._validate_stable_id(
            "result",
            self.result_id,
            self.CONTRACT_NAME,
        )
        self._validate_stable_id(
            "request",
            self.request_id,
            OllamaMultimodalRegionProcessingRequest.CONTRACT_NAME,
        )
        if not isinstance(
            self.processor_identity,
            OllamaMultimodalRegionProcessorIdentity,
        ):
            raise TypeError(
                "processor_identity must be "
                "OllamaMultimodalRegionProcessorIdentity"
            )
        if not isinstance(self.task_kind, OllamaMultimodalTaskKind):
            raise TypeError("task_kind must be OllamaMultimodalTaskKind")
        if not isinstance(self.prompt, OllamaPromptRecord):
            raise TypeError("prompt must be OllamaPromptRecord")
        if not isinstance(self.status, OllamaMultimodalResultStatus):
            raise TypeError("status must be OllamaMultimodalResultStatus")
        if not isinstance(self.cacheable, bool):
            raise TypeError("cacheable must be a boolean")
        if not isinstance(self.metadata_responses, tuple) or any(
            not isinstance(item, OllamaMetadataResponseIdentity)
            for item in self.metadata_responses
        ):
            raise TypeError(
                "metadata_responses must contain metadata identities"
            )
        stages = tuple(item.stage for item in self.metadata_responses)
        full_stages = (
            OllamaMetadataStage.PREFLIGHT_VERSION,
            OllamaMetadataStage.PREFLIGHT_TAGS,
            OllamaMetadataStage.PREFLIGHT_SHOW,
            OllamaMetadataStage.POSTFLIGHT_TAGS,
        )
        if stages != full_stages[: len(stages)]:
            raise ValueError("metadata response stages are not canonical")
        if self.model_verification is not None and (
            not isinstance(self.model_verification, OllamaModelVerification)
            or stages != full_stages
            or self.model_verification.model_name
            != self.processor_identity.model_name
            or self.model_verification.expected_model_digest
            != self.processor_identity.expected_model_digest
            or self.model_verification.ollama_version
            != self.processor_identity.expected_backend_version
        ):
            raise ValueError(
                "model verification and processor identity disagree"
            )
        if (
            not isinstance(self.selection_results, tuple)
            or not self.selection_results
            or any(
                not isinstance(item, OllamaMultimodalSelectionResult)
                for item in self.selection_results
            )
        ):
            raise ValueError(
                "selection_results must be a nonempty result tuple"
            )
        if len({item.selection_id for item in self.selection_results}) != len(
            self.selection_results
        ):
            raise ValueError("selection result IDs must be unique")
        self._validate_prompt_coverage(self.prompt, self.selection_results)
        expected_request_id = stable_id(
            OllamaMultimodalRegionProcessingRequest.CONTRACT_NAME,
            OllamaMultimodalRegionProcessingRequest.CONTRACT_VERSION,
            self.task_kind,
            tuple(
                (
                    identity.selection_id,
                    identity.source_id,
                    identity.source_blob_id,
                    identity.source_content_hash,
                    identity.page_index,
                    identity.region_id,
                    identity.png_sha256,
                    identity.png_byte_length,
                    identity.width_pixels,
                    identity.height_pixels,
                )
                for identity in (
                    item.identity for item in self.selection_results
                )
            ),
            self.prompt,
        )
        if self.request_id != expected_request_id:
            raise ValueError(
                "result request identity does not match selection provenance"
            )
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported multimodal result contract version")
        if self.evidence_status is not (
            OllamaMultimodalEvidenceStatus.AUTOMATED_UNREVIEWED
        ):
            raise ValueError("result must remain automated_unreviewed")
        if self.determinism is not OllamaMultimodalDeterminism.NONDETERMINISTIC:
            raise ValueError("result must remain nondeterministic")
        complete = all(
            item.status is OllamaMultimodalSelectionStatus.PROPOSED
            for item in self.selection_results
        )
        if self.status is OllamaMultimodalResultStatus.COMPLETE:
            if (
                not complete
                or not self.cacheable
                or self.raw_response is None
                or self.model_verification is None
            ):
                raise ValueError("complete results must be cacheable proposals")
        elif complete or self.cacheable:
            raise ValueError("failed results must be non-cacheable failures")
        expected_id = self._result_id(
            request_id=self.request_id,
            processor_identity=self.processor_identity,
            task_kind=self.task_kind,
            prompt=self.prompt,
            status=self.status,
            evidence_status=self.evidence_status,
            determinism=self.determinism,
            cacheable=self.cacheable,
            metadata_responses=self.metadata_responses,
            model_verification=self.model_verification,
            raw_response=self.raw_response,
            selection_results=self.selection_results,
        )
        if self.result_id != expected_id:
            raise ValueError("multimodal result identity mismatch")

    @staticmethod
    def _validate_stable_id(name: str, value: str, namespace: str) -> None:
        prefix = f"{namespace}:sha256:"
        if not isinstance(value, str) or not value.startswith(prefix):
            raise ValueError(f"{name} identity has an invalid namespace")
        digest = value[len(prefix) :]
        if not SHA256Hash.is_canonical(digest):
            raise ValueError(f"{name} identity must be a SHA-256 digest")

"""Exact producer-artifact verification before evidence projection."""

from dataclasses import dataclass

from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.json.limits.definition import JsonLimits
from projectkoios.ingestion.json.limits.error import JsonLimitError
from projectkoios.ingestion.json.parser import JsonParser
from projectkoios.ingestion.reference.evidence.error import (
    ReferenceEvidenceParseError,
    ReferenceEvidenceVerificationError,
)
from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.limits.error import (
    ReferenceEvidenceLimitError,
)
from projectkoios.ingestion.reference.evidence.projection.request import (
    ReferenceEvidenceProjectionRequest,
)

_ARTIFACT_JSON_LIMITS = JsonLimits(
    maximum_utf8_bytes=REFERENCE_EVIDENCE_LIMITS.maximum_bound_artifact_bytes,
    maximum_container_depth=REFERENCE_EVIDENCE_LIMITS.maximum_json_container_depth,
    maximum_items=REFERENCE_EVIDENCE_LIMITS.maximum_artifact_json_items,
    maximum_string_bytes=REFERENCE_EVIDENCE_LIMITS.maximum_bound_artifact_bytes,
    maximum_total_string_bytes=REFERENCE_EVIDENCE_LIMITS.maximum_bound_artifact_bytes,
    maximum_number_characters=REFERENCE_EVIDENCE_LIMITS.maximum_json_number_characters,
)
_ARTIFACT_JSON_PARSER = JsonParser(_ARTIFACT_JSON_LIMITS)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceProjectionArtifactVerifier:
    """Bind one projection request and verify all exact producer artifacts."""

    request: ReferenceEvidenceProjectionRequest

    def __post_init__(self) -> None:
        if type(self.request) is not ReferenceEvidenceProjectionRequest:
            raise TypeError(
                "request must be ReferenceEvidenceProjectionRequest"
            )

    def verify(self) -> None:
        """Reject malformed, noncanonical, or contradictory artifact bytes."""
        self.verify_extraction()
        request = self.request
        expected_transcript = (
            CanonicalJsonSerializer.serialize_text(request.clean_transcript)
            + "\n"
        ).encode("utf-8")
        if request.clean_transcript_result_bytes != expected_transcript:
            raise ReferenceEvidenceVerificationError(
                "serialized clean-transcript result does not match its "
                "immutable contract"
            )
        expected_audit = (
            CanonicalJsonSerializer.serialize_text(request.derivation_audit)
            + "\n"
        ).encode("utf-8")
        if request.derivation_audit_artifact != expected_audit:
            raise ReferenceEvidenceVerificationError(
                "derivation-audit artifact does not match its "
                "immutable contract"
            )

    def verify_extraction(self) -> None:
        """Verify canonical extraction JSON against its immutable result."""
        content = self.request.extraction_artifact
        try:
            value = _ARTIFACT_JSON_PARSER.parse_bytes(content)
        except JsonLimitError as error:
            raise ReferenceEvidenceLimitError(
                f"extraction artifact exceeds size limit: {error}"
            ) from error
        except JsonParseError as error:
            raise ReferenceEvidenceParseError(
                f"extraction artifact is malformed JSON: {error}"
            ) from error
        if not isinstance(value, dict):
            raise ReferenceEvidenceVerificationError(
                "extraction artifact root must be an object"
            )
        try:
            canonical = (
                CanonicalJsonSerializer.serialize_text(value) + "\n"
            ).encode("utf-8")
            if canonical != content:
                raise ReferenceEvidenceVerificationError(
                    "extraction artifact serialization is noncanonical"
                )
        except (UnicodeEncodeError, ValueError, RecursionError) as error:
            raise ReferenceEvidenceVerificationError(
                "extraction artifact cannot be canonicalized"
            ) from error
        expected = CanonicalJsonSerializer.project_object(
            self.request.extraction_result
        )
        if set(value) != set(expected):
            raise ReferenceEvidenceVerificationError(
                "extraction artifact fields do not match ExtractionResult"
            )
        if (
            value.get("document") != expected["document"]
            or value.get("warnings") != expected["warnings"]
        ):
            raise ReferenceEvidenceVerificationError(
                "extraction artifact content does not match ExtractionResult"
            )
        actual_manifest = value.get("manifest")
        expected_manifest = expected["manifest"]
        if not isinstance(actual_manifest, dict) or not isinstance(
            expected_manifest,
            dict,
        ):
            raise ReferenceEvidenceVerificationError(
                "extraction artifact manifest is malformed"
            )
        if set(actual_manifest) != set(expected_manifest):
            raise ReferenceEvidenceVerificationError(
                "extraction artifact manifest fields are unsupported"
            )
        for key, expected_value in expected_manifest.items():
            if key in {"started_at", "completed_at"}:
                actual_value = actual_manifest.get(key)
                if actual_value is not None and not isinstance(
                    actual_value, str
                ):
                    raise ReferenceEvidenceVerificationError(
                        "extraction artifact timestamps are malformed"
                    )
                continue
            if actual_manifest.get(key) != expected_value:
                raise ReferenceEvidenceVerificationError(
                    "extraction artifact manifest contradicts ExtractionResult"
                )

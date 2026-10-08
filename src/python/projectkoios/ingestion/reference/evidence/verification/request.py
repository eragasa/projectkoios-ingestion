"""Immutable request for consumer-side reference-evidence verification."""

from dataclasses import dataclass

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.limits.error import (
    ReferenceEvidenceLimitError,
)
from projectkoios.ingestion.reference.evidence.record import (
    ReferenceEvidenceRecord,
)
from projectkoios.ingestion.reference.evidence.validation import (
    REFERENCE_EVIDENCE_VALUE_REQUIREMENTS,
)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceVerificationRequest(DataObjectActionRequest):
    """Bind reusable evidence, expected source, and optional artifact bytes."""

    record: ReferenceEvidenceRecord
    source_sha256: str
    source_byte_length: int
    source_media_type: str
    extraction_artifact: bytes | None = None
    clean_transcript_result_bytes: bytes | None = None
    derivation_audit_artifact: bytes | None = None

    def __post_init__(self) -> None:
        if type(self.record) is not ReferenceEvidenceRecord:
            raise TypeError("record must be ReferenceEvidenceRecord")
        requirements = REFERENCE_EVIDENCE_VALUE_REQUIREMENTS
        requirements.require_sha256(
            self.source_sha256,
            "expected source_sha256",
        )
        requirements.require_nonnegative_int(
            self.source_byte_length,
            "expected source_byte_length",
        )
        requirements.require_text(
            self.source_media_type,
            "expected source_media_type",
        )
        for name, content in (
            ("extraction artifact", self.extraction_artifact),
            (
                "serialized clean-transcript result",
                self.clean_transcript_result_bytes,
            ),
            ("derivation-audit artifact", self.derivation_audit_artifact),
        ):
            if content is None:
                continue
            if not isinstance(content, bytes):
                raise TypeError(f"{name} must be bytes")
            if (
                len(content)
                > REFERENCE_EVIDENCE_LIMITS.maximum_bound_artifact_bytes
            ):
                raise ReferenceEvidenceLimitError(f"{name} exceeds size limit")

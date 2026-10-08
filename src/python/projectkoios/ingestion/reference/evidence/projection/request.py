"""Immutable request for complete reference-evidence projection."""

from dataclasses import dataclass

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.clean_transcript import CleanTranscript
from projectkoios.ingestion.models import ExtractionResult
from projectkoios.ingestion.provenance.audit import DerivationAuditReport
from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.limits.error import (
    ReferenceEvidenceLimitError,
)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceProjectionRequest(DataObjectActionRequest):
    """Bind exact producer records and their serialized artifact bytes."""

    extraction_result: ExtractionResult
    extraction_artifact: bytes
    clean_transcript: CleanTranscript
    clean_transcript_result_bytes: bytes
    derivation_audit: DerivationAuditReport
    derivation_audit_artifact: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.extraction_result, ExtractionResult):
            raise TypeError("extraction_result must be ExtractionResult")
        if not isinstance(self.clean_transcript, CleanTranscript):
            raise TypeError("clean_transcript must be CleanTranscript")
        if not isinstance(self.derivation_audit, DerivationAuditReport):
            raise TypeError("derivation_audit must be DerivationAuditReport")
        for name, content in (
            ("extraction artifact", self.extraction_artifact),
            ("clean-transcript result", self.clean_transcript_result_bytes),
            ("derivation-audit artifact", self.derivation_audit_artifact),
        ):
            if not isinstance(content, bytes):
                raise TypeError(f"{name} must be bytes")
            if (
                len(content)
                > REFERENCE_EVIDENCE_LIMITS.maximum_bound_artifact_bytes
            ):
                raise ReferenceEvidenceLimitError(f"{name} exceeds size limit")

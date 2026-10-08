"""Immutable clean-transcript producer evidence."""

from dataclasses import dataclass

from projectkoios.ingestion.clean_transcript import CleanTranscriptStatus
from projectkoios.ingestion.reference.evidence.artifact import (
    ReferenceEvidenceArtifact,
)
from projectkoios.ingestion.reference.evidence.layout import (
    ReferenceEvidenceLayoutIdentityInventory,
)
from projectkoios.ingestion.reference.evidence.validation import (
    REFERENCE_EVIDENCE_VALUE_REQUIREMENTS,
)

REFERENCE_EVIDENCE_CLEAN_TRANSCRIPT_MEDIA_TYPE = (
    "application/vnd.projectkoios.ingestion.clean-transcript+json"
)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceTranscript:
    """Record exact clean-transcript artifact and producer lineage."""

    artifact: ReferenceEvidenceArtifact
    result_id: str
    status: CleanTranscriptStatus
    structured_transcription_result_id: str
    layout_result_ids: ReferenceEvidenceLayoutIdentityInventory
    text_sha256: str
    text_utf8_byte_length: int
    processor_name: str
    processor_version: str
    configuration_digest: str
    warning_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.artifact, ReferenceEvidenceArtifact):
            raise TypeError("transcript artifact identity is required")
        if (
            self.artifact.media_type
            != REFERENCE_EVIDENCE_CLEAN_TRANSCRIPT_MEDIA_TYPE
        ):
            raise ValueError("unsupported transcript artifact media type")
        requirements = REFERENCE_EVIDENCE_VALUE_REQUIREMENTS
        requirements.require_text(
            self.result_id,
            "transcript result_id",
        )
        if not isinstance(self.status, CleanTranscriptStatus):
            raise TypeError("transcript status is unsupported")
        requirements.require_text(
            self.structured_transcription_result_id,
            "structured transcription result_id",
        )
        if not isinstance(
            self.layout_result_ids,
            ReferenceEvidenceLayoutIdentityInventory,
        ):
            raise TypeError(
                "transcript layout_result_ids must be a semantic inventory"
            )
        requirements.require_sha256(
            self.text_sha256,
            "transcript text_sha256",
        )
        requirements.require_nonnegative_int(
            self.text_utf8_byte_length,
            "transcript text_utf8_byte_length",
        )
        requirements.require_text(
            self.processor_name,
            "transcript processor_name",
        )
        requirements.require_text(
            self.processor_version,
            "transcript processor_version",
        )
        requirements.require_text(
            self.configuration_digest,
            "transcript configuration_digest",
        )
        requirements.require_nonnegative_int(
            self.warning_count,
            "transcript warning_count",
        )

"""Immutable extraction producer evidence."""

from dataclasses import dataclass

from projectkoios.ingestion.models import CONTRACT_VERSION, IngestionStatus
from projectkoios.ingestion.reference.evidence.artifact import (
    ReferenceEvidenceArtifact,
)
from projectkoios.ingestion.reference.evidence.validation import (
    REFERENCE_EVIDENCE_VALUE_REQUIREMENTS,
)

REFERENCE_EVIDENCE_EXTRACTION_MEDIA_TYPE = (
    "application/vnd.projectkoios.ingestion.extraction+json"
)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceExtraction:
    """Record exact extraction artifact and producer evidence."""

    artifact: ReferenceEvidenceArtifact
    contract_version: str
    manifest_id: str
    document_id: str
    status: IngestionStatus
    extractor_name: str
    extractor_version: str
    configuration_digest: str
    warning_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.artifact, ReferenceEvidenceArtifact):
            raise TypeError("extraction artifact identity is required")
        if self.artifact.media_type != REFERENCE_EVIDENCE_EXTRACTION_MEDIA_TYPE:
            raise ValueError("unsupported extraction artifact media type")
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("unsupported extraction contract version")
        requirements = REFERENCE_EVIDENCE_VALUE_REQUIREMENTS
        requirements.require_text(
            self.manifest_id,
            "extraction manifest_id",
        )
        requirements.require_text(
            self.document_id,
            "extraction document_id",
        )
        if not isinstance(self.status, IngestionStatus):
            raise TypeError("extraction status is unsupported")
        requirements.require_text(
            self.extractor_name,
            "extractor name",
        )
        requirements.require_text(
            self.extractor_version,
            "extractor version",
        )
        requirements.require_text(
            self.configuration_digest,
            "extraction configuration",
        )
        requirements.require_nonnegative_int(
            self.warning_count,
            "extraction warning_count",
        )

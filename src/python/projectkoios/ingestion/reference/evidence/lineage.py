"""Semantic audit lineage and complete-lineage verification."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from projectkoios.ingestion.clean_transcript import CleanTranscriptStatus
from projectkoios.ingestion.models import IngestionStatus
from projectkoios.ingestion.provenance.audit import DerivationAuditStatus
from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.validation import (
    REFERENCE_EVIDENCE_VALUE_REQUIREMENTS,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.reference.evidence.audit import (
        ReferenceEvidenceAudit,
    )
    from projectkoios.ingestion.reference.evidence.extraction import (
        ReferenceEvidenceExtraction,
    )
    from projectkoios.ingestion.reference.evidence.source import (
        ReferenceEvidenceSource,
    )
    from projectkoios.ingestion.reference.evidence.transcript import (
        ReferenceEvidenceTranscript,
    )


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceAuditArtifactIdentityInventory:
    """Own ordered, unique, bounded audited artifact identities."""

    _identities: tuple[str, ...] = field(repr=False)

    def __init__(self, *identities: str) -> None:
        values = tuple(identities)
        if not values:
            raise ValueError("audit audited_artifact_ids must be non-empty")
        if len(values) > REFERENCE_EVIDENCE_LIMITS.maximum_lineage_identities:
            raise ValueError("audit audited_artifact_ids is too large")
        if len(set(values)) != len(values):
            raise ValueError("audit audited_artifact_ids must be unique")
        requirements = REFERENCE_EVIDENCE_VALUE_REQUIREMENTS
        for index, identity in enumerate(values):
            requirements.require_text(
                identity,
                f"audit audited_artifact_ids[{index}]",
            )
        object.__setattr__(self, "_identities", values)

    def __iter__(self) -> Iterator[str]:
        return iter(self._identities)

    def __len__(self) -> int:
        return len(self._identities)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceLineageVerifier:
    """Validate relationships among already-validated evidence values."""

    source: ReferenceEvidenceSource
    extraction: ReferenceEvidenceExtraction
    transcript: ReferenceEvidenceTranscript
    audit: ReferenceEvidenceAudit

    def __post_init__(self) -> None:
        from projectkoios.ingestion.reference.evidence.audit import (
            ReferenceEvidenceAudit,
        )
        from projectkoios.ingestion.reference.evidence.extraction import (
            ReferenceEvidenceExtraction,
        )
        from projectkoios.ingestion.reference.evidence.source import (
            ReferenceEvidenceSource,
        )
        from projectkoios.ingestion.reference.evidence.transcript import (
            ReferenceEvidenceTranscript,
        )

        if not isinstance(self.source, ReferenceEvidenceSource):
            raise TypeError("reference-evidence source is required")
        if not isinstance(self.extraction, ReferenceEvidenceExtraction):
            raise TypeError("reference-evidence extraction is required")
        if not isinstance(self.transcript, ReferenceEvidenceTranscript):
            raise TypeError("reference-evidence transcript is required")
        if not isinstance(self.audit, ReferenceEvidenceAudit):
            raise TypeError("reference-evidence derivation audit is required")

    def require_complete(self) -> None:
        """Require exact completed producer lineage for reusable evidence."""
        if self.extraction.status is not IngestionStatus.COMPLETED:
            raise ValueError("complete evidence requires completed extraction")
        if (
            self.transcript.status
            is not CleanTranscriptStatus.AUTOMATED_UNREVIEWED
        ):
            raise ValueError(
                "complete evidence requires automated-unreviewed "
                "transcript status"
            )
        if self.audit.status is not DerivationAuditStatus.PASSED:
            raise ValueError(
                "complete evidence requires a recorded passing audit"
            )
        if self.audit.finding_count != 0:
            raise ValueError("passing derivation audit cannot contain findings")
        required_ids = {
            self.extraction.manifest_id,
            self.extraction.document_id,
            self.transcript.structured_transcription_result_id,
            self.transcript.result_id,
            *self.transcript.layout_result_ids,
        }
        if not required_ids.issubset(self.audit.audited_artifact_ids):
            raise ValueError(
                "derivation audit does not cover complete "
                "extraction/transcript lineage"
            )
        counts = {
            item.layer: item.count for item in self.audit.audited_layer_counts
        }
        required_counts = {
            "extraction_result": 1,
            "transcription_results": 1,
            "clean_transcripts": 1,
        }
        if any(
            counts.get(name) != value for name, value in required_counts.items()
        ):
            raise ValueError("derivation audit layer coverage is incomplete")
        if counts.get("layout_results") != len(
            self.transcript.layout_result_ids
        ):
            raise ValueError("derivation audit layout coverage is incomplete")

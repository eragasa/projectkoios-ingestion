"""Exact table producer evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.producer.lineage import (  # noqa: E501
    ReadingProducerLineage,
)
from projectkoios.ingestion.transcript.reading.evidence.input.visual.assessment import (  # noqa: E501
    ReadingVisualAssessment,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)
from projectkoios.ingestion.transcript.reading.evidence.table.boundary import (
    ReadingTableBoundaryKind,
)


@dataclass(frozen=True, slots=True)
class ReadingTableProducerEvidence:
    """Bind one table candidate and region to source lineage and assessment."""

    candidate_id: ReadingEvidenceIdentity
    region_id: ReadingEvidenceIdentity
    boundary_kind: ReadingTableBoundaryKind
    lineage: ReadingProducerLineage
    assessment: ReadingVisualAssessment
    record_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        roles = (
            (
                self.candidate_id,
                ReadingEvidenceIdentityKind.CANDIDATE,
                "candidate_id",
            ),
            (self.region_id, ReadingEvidenceIdentityKind.REGION, "region_id"),
        )
        for value, kind, name in roles:
            if (
                type(value) is not ReadingEvidenceIdentity
                or value.kind is not kind
            ):
                raise TypeError(f"{name} has the wrong identity role")
        if not isinstance(self.boundary_kind, ReadingTableBoundaryKind):
            raise TypeError("boundary_kind must be ReadingTableBoundaryKind")
        if type(self.lineage) is not ReadingProducerLineage:
            raise TypeError("lineage must be ReadingProducerLineage")
        if not self.lineage.artifacts:
            raise ReadingEvidenceError(
                "table requires managed artifact references"
            )
        if type(self.assessment) is not ReadingVisualAssessment:
            raise TypeError("assessment must be ReadingVisualAssessment")
        text_bytes = sum(
            len(label.encode()) for label in self.lineage.source_labels
        ) + sum(
            len(value.text.encode()) for value in self.assessment.associations
        )
        if text_bytes > READING_EVIDENCE_LIMITS.maximum_single_record_bytes:
            raise ReadingEvidenceLimitError(
                "table producer text exceeds its record limit"
            )
        object.__setattr__(
            self,
            "record_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.TABLE,
                prefix="reading-table-producer",
                material={
                    "candidate_id": self.candidate_id.value,
                    "region_id": self.region_id.value,
                    "boundary_kind": self.boundary_kind,
                    "lineage": self.lineage.identity_material(),
                    "assessment": self.assessment.identity_material(),
                },
            ),
        )

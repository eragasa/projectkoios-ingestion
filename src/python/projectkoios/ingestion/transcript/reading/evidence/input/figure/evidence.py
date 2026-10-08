"""Exact figure producer evidence."""

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


@dataclass(frozen=True, slots=True)
class ReadingFigureProducerEvidence:
    """Bind one figure candidate to exact source lineage and assessment."""

    candidate_id: ReadingEvidenceIdentity
    lineage: ReadingProducerLineage
    assessment: ReadingVisualAssessment
    record_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if type(self.candidate_id) is not ReadingEvidenceIdentity or (
            self.candidate_id.kind is not ReadingEvidenceIdentityKind.CANDIDATE
        ):
            raise TypeError("candidate_id has the wrong identity role")
        if type(self.lineage) is not ReadingProducerLineage:
            raise TypeError("lineage must be ReadingProducerLineage")
        if not self.lineage.artifacts:
            raise ReadingEvidenceError(
                "figure requires managed artifact references"
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
                "figure producer text exceeds its record limit"
            )
        object.__setattr__(
            self,
            "record_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.FIGURE,
                prefix="reading-figure-producer",
                material={
                    "candidate_id": self.candidate_id.value,
                    "lineage": self.lineage.identity_material(),
                    "assessment": self.assessment.identity_material(),
                },
            ),
        )

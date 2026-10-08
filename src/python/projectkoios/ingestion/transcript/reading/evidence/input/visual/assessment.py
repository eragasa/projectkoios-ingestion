"""Shared visual assessment producer evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.association.inventory import (  # noqa: E501
    ReadingAssociationEvidenceInventory,
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
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.status.visual import (
    ReadingVisualEvidenceStatus,
)


@dataclass(frozen=True, slots=True)
class ReadingVisualAssessment:
    """Bind exact typed associations to confidence and review state."""

    associations: ReadingAssociationEvidenceInventory
    confidence: float
    visual_status: ReadingVisualEvidenceStatus
    review_status: ReadingReviewStatus
    assessment_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if type(self.associations) is not ReadingAssociationEvidenceInventory:
            raise TypeError(
                "associations must be ReadingAssociationEvidenceInventory"
            )
        confidence = READING_EVIDENCE_LIMITS.require_confidence(
            self.confidence, "confidence"
        )
        if not isinstance(self.visual_status, ReadingVisualEvidenceStatus):
            raise TypeError("visual_status must be ReadingVisualEvidenceStatus")
        if not isinstance(self.review_status, ReadingReviewStatus):
            raise TypeError("review_status must be ReadingReviewStatus")
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(
            self,
            "assessment_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.VISUAL_ASSESSMENT,
                prefix="reading-visual-assessment",
                material={
                    "associations": self.associations.identity_material(),
                    "confidence": confidence,
                    "visual_status": self.visual_status,
                    "review_status": self.review_status,
                },
            ),
        )

    def identity_material(self) -> dict[str, object]:
        """Return ephemeral canonical assessment material."""
        return {
            "associations": self.associations.identity_material(),
            "confidence": self.confidence,
            "visual_status": self.visual_status,
            "review_status": self.review_status,
        }

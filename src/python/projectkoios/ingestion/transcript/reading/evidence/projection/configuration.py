"""Pure canonical reading evidence projection policy."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.block.text.basis import (  # noqa: E501
    ReadingTextBlockProjectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.caption.basis import (
    ReadingCaptionSelectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.equation.disposition import (  # noqa: E501
    ReadingEquationSelectionDisposition,
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
    ReadingEvidenceLimits,
)
from projectkoios.ingestion.transcript.reading.evidence.status.visual import (
    ReadingVisualEvidenceStatus,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceProjectionConfiguration:
    """Select exact text, visual, caption, equation, and limit policy."""

    text_basis: ReadingTextBlockProjectionBasis = (
        ReadingTextBlockProjectionBasis.CLEAN_PRODUCER_EXACT
    )
    caption_basis: ReadingCaptionSelectionBasis = (
        ReadingCaptionSelectionBasis.UNIQUE_NORMALIZED_ASSOCIATION
    )
    equation_disposition: ReadingEquationSelectionDisposition = (
        ReadingEquationSelectionDisposition.PRIMARY
    )
    retain_proposed_visual_evidence: bool = True
    retain_ambiguous_visual_evidence: bool = True
    retain_observed_visual_evidence: bool = True
    limits: ReadingEvidenceLimits = READING_EVIDENCE_LIMITS
    configuration_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.text_basis, ReadingTextBlockProjectionBasis):
            raise TypeError("text_basis has an unsupported type")
        if not isinstance(self.caption_basis, ReadingCaptionSelectionBasis):
            raise TypeError("caption_basis has an unsupported type")
        if not isinstance(
            self.equation_disposition, ReadingEquationSelectionDisposition
        ):
            raise TypeError("equation_disposition has an unsupported type")
        flags = (
            self.retain_proposed_visual_evidence,
            self.retain_ambiguous_visual_evidence,
            self.retain_observed_visual_evidence,
        )
        if any(type(value) is not bool for value in flags):
            raise TypeError("visual admission flags must be booleans")
        if not any(flags):
            raise ValueError(
                "at least one visual evidence status must be admitted"
            )
        if type(self.limits) is not ReadingEvidenceLimits:
            raise TypeError("limits must be ReadingEvidenceLimits")
        object.__setattr__(
            self,
            "configuration_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.PROJECTION_CONFIGURATION,
                prefix="reading-evidence-projection-configuration",
                material={
                    "text_basis": self.text_basis,
                    "caption_basis": self.caption_basis,
                    "equation_disposition": self.equation_disposition,
                    "visual_statuses": [
                        status.value
                        for status in ReadingVisualEvidenceStatus
                        if self.admits_visual_status(status)
                    ],
                    "limits": self.limits,
                },
            ),
        )

    def admits_visual_status(self, status: ReadingVisualEvidenceStatus) -> bool:
        """Return whether one exact visual producer status is admissible."""
        if not isinstance(status, ReadingVisualEvidenceStatus):
            raise TypeError("status must be ReadingVisualEvidenceStatus")
        return {
            ReadingVisualEvidenceStatus.PROPOSED: (
                self.retain_proposed_visual_evidence
            ),
            ReadingVisualEvidenceStatus.AMBIGUOUS: (
                self.retain_ambiguous_visual_evidence
            ),
            ReadingVisualEvidenceStatus.OBSERVED: (
                self.retain_observed_visual_evidence
            ),
        }[status]

"""Immutable successful reference-evidence verification result."""

from dataclasses import dataclass

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.reference.evidence.record import (
    ReferenceEvidenceRecord,
)
from projectkoios.ingestion.reference.evidence.verification.artifact import (
    ReferenceEvidenceVerifiedArtifactInventory,
)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceVerificationResult(AbstractDataObjectActionResult):
    """Return reusable evidence and exact optional-artifact coverage."""

    record: ReferenceEvidenceRecord
    verified_artifacts: ReferenceEvidenceVerifiedArtifactInventory

    def __post_init__(self) -> None:
        if type(self.record) is not ReferenceEvidenceRecord:
            raise TypeError("record must be ReferenceEvidenceRecord")
        if not isinstance(
            self.verified_artifacts,
            ReferenceEvidenceVerifiedArtifactInventory,
        ):
            raise TypeError("verified_artifacts must be a semantic inventory")

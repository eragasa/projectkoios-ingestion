"""Immutable request for reference claim-candidate projection."""

from dataclasses import dataclass

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.reference.claim.identity import (
    ResearchClaimIdentity,
)
from projectkoios.ingestion.reference.evidence.record import (
    ReferenceEvidenceRecord,
)
from projectkoios.ingestion.reference.page.location.result import (
    ReferencePageLocatorResult,
)


@dataclass(frozen=True, slots=True)
class ReferenceClaimCandidateProjectionRequest(DataObjectActionRequest):
    """Bind reusable evidence, one locator result, and one claim identity."""

    record: ReferenceEvidenceRecord
    locator_result: ReferencePageLocatorResult
    claim_identity: ResearchClaimIdentity

    def __post_init__(self) -> None:
        if type(self.record) is not ReferenceEvidenceRecord:
            raise TypeError("record must be ReferenceEvidenceRecord")
        if type(self.locator_result) is not ReferencePageLocatorResult:
            raise TypeError("locator_result must be ReferencePageLocatorResult")
        if type(self.claim_identity) is not ResearchClaimIdentity:
            raise TypeError("claim_identity must be ResearchClaimIdentity")

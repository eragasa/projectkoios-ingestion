"""Closed semantic limitations for reference claim candidates."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum


class ReferenceClaimCandidateLimitation(StrEnum):
    """One explicit limitation on a mechanical claim candidate."""

    AUTOMATED_UNREVIEWED = "automated_unreviewed"
    CITATION_CANDIDATE_ONLY = "citation_candidate_only"
    MANUAL_CLAIM_REVIEW_REQUIRED = "manual_claim_review_required"
    NOT_CLAIM_SUPPORT = "not_claim_support"
    NOT_HUMAN_PROOFREAD = "not_human_proofread"
    NOT_PUBLICATION_SUITABLE = "not_publication_suitable"
    NOT_SCIENTIFICALLY_VALIDATED = "not_scientifically_validated"


@dataclass(frozen=True, slots=True, init=False)
class ReferenceClaimCandidateLimitations:
    """Canonical immutable limitations for claim candidates."""

    _items: tuple[ReferenceClaimCandidateLimitation, ...] = field(repr=False)

    def __init__(self) -> None:
        object.__setattr__(
            self,
            "_items",
            (
                ReferenceClaimCandidateLimitation.AUTOMATED_UNREVIEWED,
                ReferenceClaimCandidateLimitation.CITATION_CANDIDATE_ONLY,
                ReferenceClaimCandidateLimitation.MANUAL_CLAIM_REVIEW_REQUIRED,
                ReferenceClaimCandidateLimitation.NOT_CLAIM_SUPPORT,
                ReferenceClaimCandidateLimitation.NOT_HUMAN_PROOFREAD,
                ReferenceClaimCandidateLimitation.NOT_PUBLICATION_SUITABLE,
                ReferenceClaimCandidateLimitation.NOT_SCIENTIFICALLY_VALIDATED,
            ),
        )

    def __iter__(self) -> Iterator[ReferenceClaimCandidateLimitation]:
        return iter(self._items)


REFERENCE_CLAIM_CANDIDATE_LIMITATIONS = ReferenceClaimCandidateLimitations()

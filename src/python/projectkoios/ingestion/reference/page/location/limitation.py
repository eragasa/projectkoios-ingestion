"""Closed semantic limitations for reference page-location results."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum


class ReferencePageLocationLimitation(StrEnum):
    """One explicit limitation on mechanical page-location evidence."""

    AUTOMATED_UNREVIEWED = "automated_unreviewed"
    NOT_CLAIM_SUPPORT = "not_claim_support"
    NOT_HUMAN_PROOFREAD = "not_human_proofread"
    NOT_PUBLICATION_SUITABLE = "not_publication_suitable"
    NOT_SCIENTIFICALLY_VALIDATED = "not_scientifically_validated"
    PAGE_NAVIGATION_ONLY = "page_navigation_only"


@dataclass(frozen=True, slots=True, init=False)
class ReferencePageLocationLimitations:
    """Canonical immutable limitations for page-location results."""

    _items: tuple[ReferencePageLocationLimitation, ...] = field(repr=False)

    def __init__(self) -> None:
        object.__setattr__(
            self,
            "_items",
            (
                ReferencePageLocationLimitation.AUTOMATED_UNREVIEWED,
                ReferencePageLocationLimitation.NOT_CLAIM_SUPPORT,
                ReferencePageLocationLimitation.NOT_HUMAN_PROOFREAD,
                ReferencePageLocationLimitation.NOT_PUBLICATION_SUITABLE,
                ReferencePageLocationLimitation.NOT_SCIENTIFICALLY_VALIDATED,
                ReferencePageLocationLimitation.PAGE_NAVIGATION_ONLY,
            ),
        )

    def __iter__(self) -> Iterator[ReferencePageLocationLimitation]:
        return iter(self._items)

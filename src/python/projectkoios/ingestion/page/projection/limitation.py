"""Mandatory non-authority limitations for page projection."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from projectkoios.ingestion.page.projection.identity import (
    PageProjectionResultIdentityDerivation,
)


class PageProjectionLimitation(StrEnum):
    """State what a text projection does not establish."""

    CLAIM_SUPPORT_NOT_ESTABLISHED = "claim_support_not_established"
    CITATION_ACCEPTANCE_NOT_ESTABLISHED = "citation_acceptance_not_established"
    PROOFREADING_NOT_ESTABLISHED = "proofreading_not_established"
    RIGHTS_NOT_ESTABLISHED = "rights_not_established"
    PUBLICATION_SUITABILITY_NOT_ESTABLISHED = (
        "publication_suitability_not_established"
    )
    SCIENTIFIC_VALIDITY_NOT_ESTABLISHED = "scientific_validity_not_established"


_PAGE_PROJECTION_LIMITATIONS = (
    PageProjectionLimitation.CLAIM_SUPPORT_NOT_ESTABLISHED,
    PageProjectionLimitation.CITATION_ACCEPTANCE_NOT_ESTABLISHED,
    PageProjectionLimitation.PROOFREADING_NOT_ESTABLISHED,
    PageProjectionLimitation.RIGHTS_NOT_ESTABLISHED,
    PageProjectionLimitation.PUBLICATION_SUITABILITY_NOT_ESTABLISHED,
    PageProjectionLimitation.SCIENTIFIC_VALIDITY_NOT_ESTABLISHED,
)


@dataclass(frozen=True, slots=True, init=False)
class PageProjectionLimitationInventory:
    """Own the complete fixed-order page-projection scope limitations."""

    _limitations: tuple[PageProjectionLimitation, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self) -> None:
        object.__setattr__(self, "_limitations", _PAGE_PROJECTION_LIMITATIONS)
        object.__setattr__(
            self,
            "inventory_id",
            PageProjectionResultIdentityDerivation.derive_limitation_inventory(
                limitations=tuple(
                    value.value for value in _PAGE_PROJECTION_LIMITATIONS
                )
            ),
        )

    def __iter__(self) -> Iterator[PageProjectionLimitation]:
        return iter(self._limitations)

    def __len__(self) -> int:
        return len(self._limitations)

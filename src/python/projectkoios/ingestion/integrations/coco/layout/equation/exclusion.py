"""Explicit exclusions from COCO formula projection."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.adaptation import (
    CocoLayoutProposalAdaptation,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


class CocoLayoutEquationExclusionCode(StrEnum):
    """Closed reasons that a formula proposal did not become a candidate."""

    BELOW_CONFIDENCE_THRESHOLD = "below_confidence_threshold"
    DUPLICATE_OVERLAP = "duplicate_overlap"


@dataclass(frozen=True, slots=True)
class CocoLayoutEquationExclusion(AbstractImmutableDataObject):
    """Retain one formula proposal excluded by deterministic projection."""

    projection_request_id: str
    adaptation: CocoLayoutProposalAdaptation
    code: CocoLayoutEquationExclusionCode
    selected_candidate_id: str | None
    exclusion_id: str = field(init=False)

    def __post_init__(self) -> None:
        request_id = LayoutValueValidation.require_text(
            "projection_request_id", self.projection_request_id
        )
        if type(self.adaptation) is not CocoLayoutProposalAdaptation:
            raise TypeError("adaptation must be CocoLayoutProposalAdaptation")
        if self.adaptation.proposal.kind is not LayoutRegionKind.EQUATION:
            raise ValueError("equation exclusion requires a formula proposal")
        if not isinstance(self.code, CocoLayoutEquationExclusionCode):
            raise TypeError("code must be CocoLayoutEquationExclusionCode")
        if self.code is CocoLayoutEquationExclusionCode.DUPLICATE_OVERLAP:
            selected = LayoutValueValidation.require_text(
                "selected_candidate_id", self.selected_candidate_id
            )
        else:
            if self.selected_candidate_id is not None:
                raise ValueError(
                    "confidence exclusion cannot identify another candidate"
                )
            selected = None
        object.__setattr__(
            self,
            "exclusion_id",
            stable_id(
                "coco-layout-equation-exclusion",
                request_id,
                self.adaptation.adaptation_id,
                self.code,
                selected,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutEquationExclusionInventory:
    """Own canonical formula-projection exclusions."""

    _exclusions: tuple[CocoLayoutEquationExclusion, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *exclusions: CocoLayoutEquationExclusion) -> None:
        values = tuple(exclusions)
        if any(
            type(value) is not CocoLayoutEquationExclusion for value in values
        ):
            raise TypeError("exclusion inventory requires exact exclusions")
        identities = tuple(value.exclusion_id for value in values)
        if len(identities) != len(set(identities)):
            raise ValueError("equation exclusion identities must be unique")
        order = tuple(
            (
                value.adaptation.proposal.proposal_id,
                value.code,
                value.exclusion_id,
            )
            for value in values
        )
        if order != tuple(sorted(order)):
            raise ValueError("equation exclusions must use canonical order")
        object.__setattr__(self, "_exclusions", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id("coco-layout-equation-exclusion-inventory", identities),
        )

    def __iter__(self) -> Iterator[CocoLayoutEquationExclusion]:
        return iter(self._exclusions)

    def __len__(self) -> int:
        return len(self._exclusions)

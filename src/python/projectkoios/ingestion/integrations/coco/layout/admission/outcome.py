"""Independent per-category outcomes from COCO region admission."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.adaptation import (
    CocoLayoutProposalAdaptationInventory,
)
from projectkoios.ingestion.integrations.coco.layout.category import (
    CocoLayoutCategory,
)
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_CATEGORIES,
)

from .evidence import (
    CocoLayoutRegionAdmissionDisposition,
    CocoLayoutRegionAdmissionEvidenceInventory,
)


class CocoLayoutCategoryAdmissionStatus(StrEnum):
    """Closed status for one category without whole-page authority."""

    ADMITTED = "admitted"
    EMPTY = "empty"
    ESCALATION_REQUIRED = "escalation_required"


@dataclass(frozen=True, slots=True)
class CocoLayoutCategoryAdmission(AbstractImmutableDataObject):
    """Aggregate one category while retaining every supported detection."""

    category: CocoLayoutCategory
    status: CocoLayoutCategoryAdmissionStatus
    evidence: CocoLayoutRegionAdmissionEvidenceInventory
    outcome_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.category) is not CocoLayoutCategory:
            raise TypeError("category must be CocoLayoutCategory")
        if not isinstance(self.status, CocoLayoutCategoryAdmissionStatus):
            raise TypeError("status must be a category admission status")
        if type(self.evidence) is not (
            CocoLayoutRegionAdmissionEvidenceInventory
        ):
            raise TypeError("evidence must be an admission inventory")
        if any(
            item.adaptation.detection.category_id != self.category.category_id
            for item in self.evidence
        ):
            raise ValueError("category admission contains another category")
        dispositions = tuple(item.disposition for item in self.evidence)
        if (
            CocoLayoutRegionAdmissionDisposition.ESCALATION_REQUIRED_LIMIT
            in dispositions
        ):
            expected = CocoLayoutCategoryAdmissionStatus.ESCALATION_REQUIRED
        elif CocoLayoutRegionAdmissionDisposition.ADMITTED in dispositions:
            expected = CocoLayoutCategoryAdmissionStatus.ADMITTED
        else:
            expected = CocoLayoutCategoryAdmissionStatus.EMPTY
        if self.status is not expected:
            raise ValueError("category status differs from its evidence")
        if expected is CocoLayoutCategoryAdmissionStatus.ESCALATION_REQUIRED:
            if CocoLayoutRegionAdmissionDisposition.ADMITTED in dispositions:
                raise ValueError("escalated category cannot admit regions")
        object.__setattr__(
            self,
            "outcome_id",
            stable_id(
                "coco-layout-category-admission",
                self.category.category_identity,
                self.status,
                self.evidence.inventory_id,
            ),
        )

    @property
    def admitted_adaptations(self) -> CocoLayoutProposalAdaptationInventory:
        """Return semantically admitted adaptations for this category."""
        return CocoLayoutProposalAdaptationInventory(
            *(
                item.adaptation
                for item in self.evidence
                if item.disposition
                is CocoLayoutRegionAdmissionDisposition.ADMITTED
            )
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutCategoryAdmissionInventory:
    """Own one outcome for every profile category in registry order."""

    _outcomes: tuple[CocoLayoutCategoryAdmission, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *outcomes: CocoLayoutCategoryAdmission) -> None:
        values = tuple(outcomes)
        if not values:
            raise ValueError("category admission inventory must be non-empty")
        if len(values) > MAX_COCO_LAYOUT_CATEGORIES:
            raise ValueError("category admissions exceed the category limit")
        if any(
            type(value) is not CocoLayoutCategoryAdmission for value in values
        ):
            raise TypeError("category inventory requires exact outcomes")
        category_ids = tuple(value.category.category_id for value in values)
        if category_ids != tuple(sorted(category_ids)):
            raise ValueError("category admissions must follow registry order")
        if len(category_ids) != len(set(category_ids)):
            raise ValueError("category admissions must be unique")
        object.__setattr__(self, "_outcomes", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "coco-layout-category-admission-inventory",
                tuple(value.outcome_id for value in values),
            ),
        )

    def __iter__(self) -> Iterator[CocoLayoutCategoryAdmission]:
        return iter(self._outcomes)

    def __len__(self) -> int:
        return len(self._outcomes)

    def require(self, category_id: int) -> CocoLayoutCategoryAdmission:
        """Return one exact category outcome or reject an unknown ID."""
        for outcome in self._outcomes:
            if outcome.category.category_id == category_id:
                return outcome
        raise ValueError("admission result has no such profile category")

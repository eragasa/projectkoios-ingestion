"""Pinned COCO category mappings for document-layout detection."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_CATEGORIES,
    MAX_COCO_LAYOUT_CATEGORY_NAME_CHARACTERS,
    MAX_COCO_LAYOUT_CATEGORY_NAME_TOTAL_CHARACTERS,
)
from projectkoios.ingestion.integrations.coco.layout.limits.error import (
    CocoLayoutLimitError,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class CocoLayoutCategory(AbstractImmutableDataObject):
    """Map one exact COCO category ID and name to a layout-region kind."""

    category_id: int
    name: str
    kind: LayoutRegionKind
    category_identity: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.category_id, bool)
            or not isinstance(self.category_id, int)
            or self.category_id < 0
        ):
            raise ValueError("category_id must be a non-negative integer")
        name = LayoutValueValidation.require_text("name", self.name)
        if len(name) > MAX_COCO_LAYOUT_CATEGORY_NAME_CHARACTERS:
            raise CocoLayoutLimitError(
                "COCO category name exceeds its character limit"
            )
        if not isinstance(self.kind, LayoutRegionKind):
            raise TypeError("kind must be LayoutRegionKind")
        object.__setattr__(
            self,
            "category_identity",
            stable_id(
                "coco-layout-category",
                self.category_id,
                name,
                self.kind,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutCategoryInventory:
    """Own one ordered, unique, bounded COCO category registry."""

    _categories: tuple[CocoLayoutCategory, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *categories: CocoLayoutCategory) -> None:
        values = tuple(categories)
        if not values:
            raise ValueError("COCO category inventory must be non-empty")
        if len(values) > MAX_COCO_LAYOUT_CATEGORIES:
            raise CocoLayoutLimitError(
                "COCO category inventory exceeds its count limit"
            )
        if any(type(value) is not CocoLayoutCategory for value in values):
            raise TypeError("COCO category inventory requires exact categories")
        ids = tuple(value.category_id for value in values)
        if ids != tuple(sorted(ids)):
            raise ValueError("COCO categories must be sorted by category_id")
        if len(ids) != len(set(ids)):
            raise ValueError("COCO category IDs must be unique")
        names = tuple(value.name for value in values)
        if len(names) != len(set(names)):
            raise ValueError("COCO category names must be unique")
        if sum(len(name) for name in names) > (
            MAX_COCO_LAYOUT_CATEGORY_NAME_TOTAL_CHARACTERS
        ):
            raise CocoLayoutLimitError(
                "COCO category names exceed their aggregate limit"
            )
        object.__setattr__(self, "_categories", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "coco-layout-category-inventory",
                tuple(value.category_identity for value in values),
            ),
        )

    def __iter__(self) -> Iterator[CocoLayoutCategory]:
        return iter(self._categories)

    def __len__(self) -> int:
        return len(self._categories)

    def require(self, category_id: int) -> CocoLayoutCategory:
        """Return one exact category or reject an unknown ID."""
        for category in self._categories:
            if category.category_id == category_id:
                return category
        raise ValueError("COCO detection references an unknown category")

    @classmethod
    def doclaynet_v1(cls) -> CocoLayoutCategoryInventory:
        """Return the pinned eleven-category DocLayNet v1 mapping."""
        return cls(
            CocoLayoutCategory(1, "Caption", LayoutRegionKind.CAPTION),
            CocoLayoutCategory(2, "Footnote", LayoutRegionKind.FOOTNOTE),
            CocoLayoutCategory(3, "Formula", LayoutRegionKind.EQUATION),
            CocoLayoutCategory(4, "List-item", LayoutRegionKind.LIST),
            CocoLayoutCategory(5, "Page-footer", LayoutRegionKind.FOOTER),
            CocoLayoutCategory(6, "Page-header", LayoutRegionKind.HEADER),
            CocoLayoutCategory(7, "Picture", LayoutRegionKind.FIGURE),
            CocoLayoutCategory(
                8,
                "Section-header",
                LayoutRegionKind.TITLE,
            ),
            CocoLayoutCategory(9, "Table", LayoutRegionKind.TABLE),
            CocoLayoutCategory(10, "Text", LayoutRegionKind.TEXT),
            CocoLayoutCategory(11, "Title", LayoutRegionKind.TITLE),
        )

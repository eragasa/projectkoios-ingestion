"""Semantic regions supplied to deterministic reading-order resolution."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

from .block import LayoutReadingOrderBlockInventory
from .limits import MAX_LAYOUT_READING_ORDER_ELEMENTS


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderRegion(AbstractImmutableDataObject):
    """Bind one semantic region to geometry and assigned native blocks."""

    region_id: str
    kind: LayoutRegionKind
    bounding_box_pixels: tuple[float, float, float, float]
    blocks: LayoutReadingOrderBlockInventory
    evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        identity = LayoutValueValidation.require_text(
            "region_id", self.region_id
        )
        if not isinstance(self.kind, LayoutRegionKind):
            raise TypeError("kind must be LayoutRegionKind")
        box = LayoutValueValidation.require_box(
            "bounding_box_pixels", self.bounding_box_pixels
        )
        if type(self.blocks) is not LayoutReadingOrderBlockInventory:
            raise TypeError("blocks must be LayoutReadingOrderBlockInventory")
        object.__setattr__(self, "region_id", identity)
        object.__setattr__(self, "bounding_box_pixels", box)
        object.__setattr__(
            self,
            "evidence_id",
            stable_id(
                "layout-reading-order-region",
                identity,
                self.kind,
                box,
                self.blocks.inventory_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderRegionInventory:
    """Own unique semantic regions in upstream declaration order."""

    _regions: tuple[LayoutReadingOrderRegion, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *regions: LayoutReadingOrderRegion) -> None:
        values = tuple(regions)
        if len(values) > MAX_LAYOUT_READING_ORDER_ELEMENTS:
            raise ValueError(
                "reading-order regions exceed implementation limit"
            )
        if any(
            type(region) is not LayoutReadingOrderRegion for region in values
        ):
            raise TypeError("regions must be LayoutReadingOrderRegion values")
        region_ids = tuple(region.region_id for region in values)
        if len(region_ids) != len(set(region_ids)):
            raise ValueError("reading-order region IDs must be unique")
        object.__setattr__(self, "_regions", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "layout-reading-order-region-inventory",
                tuple(region.evidence_id for region in values),
            ),
        )

    def __iter__(self) -> Iterator[LayoutReadingOrderRegion]:
        return iter(self._regions)

    def __len__(self) -> int:
        return len(self._regions)

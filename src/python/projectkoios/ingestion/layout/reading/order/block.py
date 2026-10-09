"""Native-block geometry and expected-coverage inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

from .limits import MAX_LAYOUT_READING_ORDER_ELEMENTS


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderBlock(AbstractImmutableDataObject):
    """Bind one native block to exact render-space geometry."""

    block_id: str
    bounding_box_pixels: tuple[float, float, float, float]
    evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        identity = LayoutValueValidation.require_text("block_id", self.block_id)
        box = LayoutValueValidation.require_box(
            "bounding_box_pixels", self.bounding_box_pixels
        )
        object.__setattr__(self, "block_id", identity)
        object.__setattr__(self, "bounding_box_pixels", box)
        object.__setattr__(
            self,
            "evidence_id",
            stable_id("layout-reading-order-block", identity, box),
        )


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderBlockInventory:
    """Own unique native blocks in producer declaration order."""

    _blocks: tuple[LayoutReadingOrderBlock, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *blocks: LayoutReadingOrderBlock) -> None:
        values = tuple(blocks)
        if len(values) > MAX_LAYOUT_READING_ORDER_ELEMENTS:
            raise ValueError("native blocks exceed implementation limit")
        if any(type(block) is not LayoutReadingOrderBlock for block in values):
            raise TypeError("blocks must be LayoutReadingOrderBlock values")
        block_ids = tuple(block.block_id for block in values)
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("native block IDs must be unique per region")
        object.__setattr__(self, "_blocks", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "layout-reading-order-block-inventory",
                tuple(block.evidence_id for block in values),
            ),
        )

    def __iter__(self) -> Iterator[LayoutReadingOrderBlock]:
        return iter(self._blocks)

    def __len__(self) -> int:
        return len(self._blocks)


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderExpectedBlockInventory:
    """Own the complete native-block identity set expected in the result."""

    _block_ids: tuple[str, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *block_ids: str) -> None:
        if len(block_ids) > MAX_LAYOUT_READING_ORDER_ELEMENTS:
            raise ValueError(
                "expected native blocks exceed implementation limit"
            )
        values = tuple(
            LayoutValueValidation.require_text("block_id", block_id)
            for block_id in block_ids
        )
        if len(values) != len(set(values)):
            raise ValueError("expected native block IDs must be unique")
        object.__setattr__(self, "_block_ids", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id("layout-reading-order-expected-blocks", values),
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self._block_ids)

    def __len__(self) -> int:
        return len(self._block_ids)

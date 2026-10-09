"""Complete deterministic reading-order resolution values."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

from .limits import MAX_LAYOUT_READING_ORDER_ELEMENTS


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderRegionSequence:
    """Own one complete resolved semantic-region order."""

    _region_ids: tuple[str, ...] = field(repr=True)
    sequence_id: str = field(init=False)

    def __init__(self, *region_ids: str) -> None:
        if len(region_ids) > MAX_LAYOUT_READING_ORDER_ELEMENTS:
            raise ValueError(
                "resolved region order exceeds implementation limit"
            )
        values = tuple(
            LayoutValueValidation.require_text("region_id", region_id)
            for region_id in region_ids
        )
        if len(values) != len(set(values)):
            raise ValueError("resolved region IDs must be unique")
        object.__setattr__(self, "_region_ids", values)
        object.__setattr__(
            self,
            "sequence_id",
            stable_id("layout-reading-order-region-sequence", values),
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self._region_ids)

    def __len__(self) -> int:
        return len(self._region_ids)


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderNativeBlockSequence:
    """Own one complete resolved native-block order."""

    _block_ids: tuple[str, ...] = field(repr=True)
    sequence_id: str = field(init=False)

    def __init__(self, *block_ids: str) -> None:
        if len(block_ids) > MAX_LAYOUT_READING_ORDER_ELEMENTS:
            raise ValueError(
                "resolved block order exceeds implementation limit"
            )
        values = tuple(
            LayoutValueValidation.require_text("block_id", block_id)
            for block_id in block_ids
        )
        if len(values) != len(set(values)):
            raise ValueError("resolved native block IDs must be unique")
        object.__setattr__(self, "_block_ids", values)
        object.__setattr__(
            self,
            "sequence_id",
            stable_id("layout-reading-order-block-sequence", values),
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self._block_ids)

    def __len__(self) -> int:
        return len(self._block_ids)


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderResolution(AbstractImmutableDataObject):
    """Bind complete region and native-block permutations."""

    region_order: LayoutReadingOrderRegionSequence
    native_block_order: LayoutReadingOrderNativeBlockSequence
    resolution_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.region_order) is not LayoutReadingOrderRegionSequence:
            raise TypeError("region_order must be a resolved region sequence")
        if (
            type(self.native_block_order)
            is not LayoutReadingOrderNativeBlockSequence
        ):
            raise TypeError(
                "native_block_order must be a resolved block sequence"
            )
        object.__setattr__(
            self,
            "resolution_id",
            stable_id(
                "layout-reading-order-resolution",
                self.region_order.sequence_id,
                self.native_block_order.sequence_id,
            ),
        )

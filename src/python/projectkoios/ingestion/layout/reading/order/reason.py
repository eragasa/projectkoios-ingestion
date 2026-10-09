"""Deterministic reading-order escalation reason inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.identity import stable_id

from .kind import LayoutReadingOrderReason


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderReasonInventory:
    """Own sorted unique deterministic escalation reasons."""

    _reasons: tuple[LayoutReadingOrderReason, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *reasons: LayoutReadingOrderReason) -> None:
        values = tuple(reasons)
        if any(
            not isinstance(reason, LayoutReadingOrderReason)
            for reason in values
        ):
            raise TypeError("reasons must be LayoutReadingOrderReason values")
        if values != tuple(sorted(set(values), key=str)):
            raise ValueError("reading-order reasons must be unique and sorted")
        object.__setattr__(self, "_reasons", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id("layout-reading-order-reason-inventory", values),
        )

    def __iter__(self) -> Iterator[LayoutReadingOrderReason]:
        return iter(self._reasons)

    def __len__(self) -> int:
        return len(self._reasons)

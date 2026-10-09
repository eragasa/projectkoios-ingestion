"""Declared replica slots for complete missing-evidence accounting."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id

from .judgment import LayoutReadingOrderNormalizedReplicaJudgment
from .limits import MAX_LAYOUT_READING_ORDER_EVALUATION_REPLICAS


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderReplicaJudgmentSlot(AbstractImmutableDataObject):
    """Bind one declared replica position to present or missing evidence."""

    replica_index: int
    judgment: LayoutReadingOrderNormalizedReplicaJudgment | None
    slot_id: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.replica_index, bool)
            or not isinstance(self.replica_index, int)
            or self.replica_index < 0
            or self.replica_index
            >= MAX_LAYOUT_READING_ORDER_EVALUATION_REPLICAS
        ):
            raise ValueError(
                "replica_index is outside the implementation limit"
            )
        if self.judgment is not None and type(self.judgment) is not (
            LayoutReadingOrderNormalizedReplicaJudgment
        ):
            raise TypeError("judgment must be normalized replica evidence")
        object.__setattr__(
            self,
            "slot_id",
            stable_id(
                "layout-reading-order-replica-judgment-slot",
                self.replica_index,
                None if self.judgment is None else self.judgment.record_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderReplicaJudgmentSlotInventory:
    """Own at least two contiguous declared replica slots."""

    _slots: tuple[LayoutReadingOrderReplicaJudgmentSlot, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *slots: LayoutReadingOrderReplicaJudgmentSlot) -> None:
        values = tuple(slots)
        if not 2 <= len(values) <= MAX_LAYOUT_READING_ORDER_EVALUATION_REPLICAS:
            raise ValueError(
                "evaluation requires between two and sixteen replica slots"
            )
        if any(
            type(slot) is not LayoutReadingOrderReplicaJudgmentSlot
            for slot in values
        ):
            raise TypeError("slots must be replica judgment slots")
        if tuple(slot.replica_index for slot in values) != tuple(
            range(len(values))
        ):
            raise ValueError("replica indexes must be contiguous and ordered")
        object.__setattr__(self, "_slots", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "layout-reading-order-replica-judgment-slot-inventory",
                tuple(slot.slot_id for slot in values),
            ),
        )

    def __iter__(self) -> Iterator[LayoutReadingOrderReplicaJudgmentSlot]:
        return iter(self._slots)

    def __len__(self) -> int:
        return len(self._slots)

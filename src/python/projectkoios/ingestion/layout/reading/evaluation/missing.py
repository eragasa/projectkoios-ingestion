"""Missing normalized replica evidence reporting."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id

from .limits import MAX_LAYOUT_READING_ORDER_EVALUATION_REPLICAS


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderMissingReplicaEvidence(AbstractImmutableDataObject):
    """Identify one declared slot with no normalized judgment."""

    replica_index: int
    evidence_id: str = field(init=False)

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
        object.__setattr__(
            self,
            "evidence_id",
            stable_id(
                "layout-reading-order-missing-replica-evidence",
                self.replica_index,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderMissingReplicaEvidenceInventory:
    """Own missing evidence in unique replica-index order."""

    _evidence: tuple[LayoutReadingOrderMissingReplicaEvidence, ...] = field(
        repr=True
    )
    inventory_id: str = field(init=False)

    def __init__(
        self, *evidence: LayoutReadingOrderMissingReplicaEvidence
    ) -> None:
        values = tuple(evidence)
        if any(
            type(item) is not LayoutReadingOrderMissingReplicaEvidence
            for item in values
        ):
            raise TypeError("evidence must be missing replica evidence")
        indexes = tuple(item.replica_index for item in values)
        if tuple(sorted(indexes)) != indexes or len(indexes) != len(
            set(indexes)
        ):
            raise ValueError("missing evidence must use unique sorted indexes")
        object.__setattr__(self, "_evidence", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "layout-reading-order-missing-replica-evidence-inventory",
                tuple(item.evidence_id for item in values),
            ),
        )

    def __iter__(self) -> Iterator[LayoutReadingOrderMissingReplicaEvidence]:
        return iter(self._evidence)

    def __len__(self) -> int:
        return len(self._evidence)

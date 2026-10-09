"""Per-replica candidate alignment evidence."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id

from .judgment import LayoutReadingOrderReplicaJudgmentKind
from .limits import (
    MAX_LAYOUT_READING_ORDER_EVALUATION_REPLICAS,
    MAX_LAYOUT_READING_ORDER_EVIDENCE_ID_CHARACTERS,
)
from .sequence import LayoutReadingOrderNormalizedElementSequence


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderCandidateContradiction(AbstractImmutableDataObject):
    """Retain one claimed precedence that contradicts the candidate order."""

    claimed_before_element_id: str
    claimed_after_element_id: str
    contradiction_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.claimed_before_element_id, str
        ) or not isinstance(self.claimed_after_element_id, str):
            raise TypeError("contradiction element IDs must be strings")
        if (
            not self.claimed_before_element_id
            or not self.claimed_after_element_id
            or self.claimed_before_element_id == self.claimed_after_element_id
        ):
            raise ValueError("contradiction requires two distinct element IDs")
        object.__setattr__(
            self,
            "contradiction_id",
            stable_id(
                "layout-reading-order-candidate-contradiction",
                self.claimed_before_element_id,
                self.claimed_after_element_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderCandidateContradictionInventory:
    """Own candidate contradictions in deterministic candidate-pair order."""

    _contradictions: tuple[LayoutReadingOrderCandidateContradiction, ...] = (
        field(repr=True)
    )
    inventory_id: str = field(init=False)

    def __init__(
        self, *contradictions: LayoutReadingOrderCandidateContradiction
    ) -> None:
        values = tuple(contradictions)
        if any(
            type(item) is not LayoutReadingOrderCandidateContradiction
            for item in values
        ):
            raise TypeError(
                "contradictions must be candidate contradiction values"
            )
        ids = tuple(item.contradiction_id for item in values)
        if len(ids) != len(set(ids)):
            raise ValueError("candidate contradictions must be unique")
        object.__setattr__(self, "_contradictions", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "layout-reading-order-candidate-contradiction-inventory", ids
            ),
        )

    def __iter__(self) -> Iterator[LayoutReadingOrderCandidateContradiction]:
        return iter(self._contradictions)

    def __len__(self) -> int:
        return len(self._contradictions)


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderReplicaAlignment(AbstractImmutableDataObject):
    """Preserve one valid replica's normalized candidate alignment."""

    replica_index: int
    normalized_replica_evidence_id: str
    judgment: LayoutReadingOrderReplicaJudgmentKind
    covered_elements: LayoutReadingOrderNormalizedElementSequence
    claimed_order: LayoutReadingOrderNormalizedElementSequence | None
    contradictions: LayoutReadingOrderCandidateContradictionInventory
    alignment_id: str = field(init=False)

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
        if (
            not isinstance(self.normalized_replica_evidence_id, str)
            or not self.normalized_replica_evidence_id
        ):
            raise ValueError("alignment requires a replica evidence identity")
        if (
            len(self.normalized_replica_evidence_id)
            > MAX_LAYOUT_READING_ORDER_EVIDENCE_ID_CHARACTERS
        ):
            raise ValueError(
                "replica evidence identity exceeds implementation limit"
            )
        if any(
            ord(character) < 32
            for character in self.normalized_replica_evidence_id
        ):
            raise ValueError(
                "replica evidence identity contains control characters"
            )
        if not isinstance(self.judgment, LayoutReadingOrderReplicaJudgmentKind):
            raise TypeError("judgment uses an invalid enum")
        if (
            type(self.covered_elements)
            is not LayoutReadingOrderNormalizedElementSequence
        ):
            raise TypeError("covered_elements must be a normalized sequence")
        if (
            self.claimed_order is not None
            and type(self.claimed_order)
            is not LayoutReadingOrderNormalizedElementSequence
        ):
            raise TypeError("claimed_order must be a normalized sequence")
        if (
            type(self.contradictions)
            is not LayoutReadingOrderCandidateContradictionInventory
        ):
            raise TypeError("contradictions must be a contradiction inventory")
        if (
            self.judgment
            is LayoutReadingOrderReplicaJudgmentKind.DISAGREES_WITH_CANDIDATE
        ):
            if len(self.contradictions) == 0:
                raise ValueError(
                    "disagreement requires candidate contradictions"
                )
        elif len(self.contradictions) != 0:
            raise ValueError(
                "only disagreement may carry candidate contradictions"
            )
        object.__setattr__(
            self,
            "alignment_id",
            stable_id(
                "layout-reading-order-replica-alignment",
                self.replica_index,
                self.normalized_replica_evidence_id,
                self.judgment,
                self.covered_elements.sequence_id,
                None
                if self.claimed_order is None
                else self.claimed_order.sequence_id,
                self.contradictions.inventory_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderReplicaAlignmentInventory:
    """Own valid replica alignments in replica-index order."""

    _alignments: tuple[LayoutReadingOrderReplicaAlignment, ...] = field(
        repr=True
    )
    inventory_id: str = field(init=False)

    def __init__(self, *alignments: LayoutReadingOrderReplicaAlignment) -> None:
        values = tuple(alignments)
        if any(
            type(item) is not LayoutReadingOrderReplicaAlignment
            for item in values
        ):
            raise TypeError("alignments must be replica alignment values")
        indexes = tuple(item.replica_index for item in values)
        if tuple(sorted(indexes)) != indexes or len(indexes) != len(
            set(indexes)
        ):
            raise ValueError(
                "alignments must use unique sorted replica indexes"
            )
        identities = tuple(
            item.normalized_replica_evidence_id for item in values
        )
        if len(identities) != len(set(identities)):
            raise ValueError(
                "valid alignments require distinct evidence identities"
            )
        object.__setattr__(self, "_alignments", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "layout-reading-order-replica-alignment-inventory",
                tuple(item.alignment_id for item in values),
            ),
        )

    def __iter__(self) -> Iterator[LayoutReadingOrderReplicaAlignment]:
        return iter(self._alignments)

    def __len__(self) -> int:
        return len(self._alignments)

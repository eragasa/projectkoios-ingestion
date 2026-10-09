"""Malformed normalized replica evidence reporting."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id

from .limits import (
    MAX_LAYOUT_READING_ORDER_EVALUATION_REPLICAS,
    MAX_LAYOUT_READING_ORDER_EVIDENCE_ID_CHARACTERS,
)


class LayoutReadingOrderMalformedReplicaReason(StrEnum):
    """Closed deterministic reasons that normalized evidence is unusable."""

    EMPTY_NORMALIZED_REPLICA_EVIDENCE_ID = (
        "empty_normalized_replica_evidence_id"
    )
    WRONG_CANDIDATE_ORDER = "wrong_candidate_order"
    EMPTY_COVERED_ELEMENT_ID = "empty_covered_element_id"
    UNKNOWN_COVERED_ELEMENT_ID = "unknown_covered_element_id"
    DUPLICATE_COVERED_ELEMENT_ID = "duplicate_covered_element_id"
    EMPTY_CLAIMED_ELEMENT_ID = "empty_claimed_element_id"
    UNKNOWN_CLAIMED_ELEMENT_ID = "unknown_claimed_element_id"
    DUPLICATE_CLAIMED_ELEMENT_ID = "duplicate_claimed_element_id"
    CLAIMED_ORDER_COVERAGE_MISMATCH = "claimed_order_coverage_mismatch"
    CLAIMED_ORDER_REQUIRED = "claimed_order_required"
    CLAIMED_ORDER_FORBIDDEN = "claimed_order_forbidden"
    DECLARED_AGREEMENT_MISMATCH = "declared_agreement_mismatch"
    DECLARED_DISAGREEMENT_MISMATCH = "declared_disagreement_mismatch"
    DUPLICATE_NORMALIZED_REPLICA_EVIDENCE_ID = (
        "duplicate_normalized_replica_evidence_id"
    )


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderMalformedReplicaReasonInventory:
    """Own sorted unique malformed-evidence reasons."""

    _reasons: tuple[LayoutReadingOrderMalformedReplicaReason, ...] = field(
        repr=True
    )
    inventory_id: str = field(init=False)

    def __init__(
        self, *reasons: LayoutReadingOrderMalformedReplicaReason
    ) -> None:
        values = tuple(reasons)
        if not values:
            raise ValueError("malformed evidence requires at least one reason")
        if any(
            not isinstance(reason, LayoutReadingOrderMalformedReplicaReason)
            for reason in values
        ):
            raise TypeError("malformed evidence reason uses an invalid enum")
        if (
            len(values) != len(set(values))
            or tuple(sorted(values, key=str)) != values
        ):
            raise ValueError(
                "malformed evidence reasons must be sorted and unique"
            )
        object.__setattr__(self, "_reasons", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "layout-reading-order-malformed-reason-inventory", values
            ),
        )

    def __iter__(self) -> Iterator[LayoutReadingOrderMalformedReplicaReason]:
        return iter(self._reasons)

    def __len__(self) -> int:
        return len(self._reasons)


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderMalformedReplicaEvidence(AbstractImmutableDataObject):
    """Report one unusable normalized judgment without repairing it."""

    replica_index: int
    normalized_replica_evidence_id: str
    reasons: LayoutReadingOrderMalformedReplicaReasonInventory
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
        if not isinstance(self.normalized_replica_evidence_id, str):
            raise TypeError("normalized_replica_evidence_id must be a string")
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
        if (
            type(self.reasons)
            is not LayoutReadingOrderMalformedReplicaReasonInventory
        ):
            raise TypeError("reasons must be a malformed reason inventory")
        object.__setattr__(
            self,
            "evidence_id",
            stable_id(
                "layout-reading-order-malformed-replica-evidence",
                self.replica_index,
                self.normalized_replica_evidence_id,
                self.reasons.inventory_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderMalformedReplicaEvidenceInventory:
    """Own malformed evidence in replica-index order."""

    _evidence: tuple[LayoutReadingOrderMalformedReplicaEvidence, ...] = field(
        repr=True
    )
    inventory_id: str = field(init=False)

    def __init__(
        self, *evidence: LayoutReadingOrderMalformedReplicaEvidence
    ) -> None:
        values = tuple(evidence)
        if any(
            type(item) is not LayoutReadingOrderMalformedReplicaEvidence
            for item in values
        ):
            raise TypeError("evidence must be malformed replica evidence")
        indexes = tuple(item.replica_index for item in values)
        if tuple(sorted(indexes)) != indexes or len(indexes) != len(
            set(indexes)
        ):
            raise ValueError(
                "malformed evidence must use unique sorted indexes"
            )
        object.__setattr__(self, "_evidence", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "layout-reading-order-malformed-replica-evidence-inventory",
                tuple(item.evidence_id for item in values),
            ),
        )

    def __iter__(self) -> Iterator[LayoutReadingOrderMalformedReplicaEvidence]:
        return iter(self._evidence)

    def __len__(self) -> int:
        return len(self._evidence)

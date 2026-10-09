"""Agent-normalized replica judgments accepted as opaque evaluation input."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id

from .limits import MAX_LAYOUT_READING_ORDER_EVIDENCE_ID_CHARACTERS
from .sequence import LayoutReadingOrderNormalizedElementSequence


class LayoutReadingOrderReplicaJudgmentKind(StrEnum):
    """Closed normalized alignment judgment supplied by an external owner."""

    AGREES_WITH_CANDIDATE = "agrees_with_candidate"
    DISAGREES_WITH_CANDIDATE = "disagrees_with_candidate"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderNormalizedReplicaJudgment(AbstractImmutableDataObject):
    """Retain normalized semantics without importing Agent or Search types."""

    normalized_replica_evidence_id: str
    candidate_order_id: str
    covered_elements: LayoutReadingOrderNormalizedElementSequence
    claimed_order: LayoutReadingOrderNormalizedElementSequence | None
    judgment: LayoutReadingOrderReplicaJudgmentKind
    record_id: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "normalized_replica_evidence_id",
            "candidate_order_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
            if len(value) > MAX_LAYOUT_READING_ORDER_EVIDENCE_ID_CHARACTERS:
                raise ValueError(f"{name} exceeds implementation limit")
            if any(ord(character) < 32 for character in value):
                raise ValueError(f"{name} contains control characters")
        if type(self.covered_elements) is not (
            LayoutReadingOrderNormalizedElementSequence
        ):
            raise TypeError("covered_elements must be a normalized sequence")
        if self.claimed_order is not None and type(self.claimed_order) is not (
            LayoutReadingOrderNormalizedElementSequence
        ):
            raise TypeError("claimed_order must be a normalized sequence")
        if not isinstance(self.judgment, LayoutReadingOrderReplicaJudgmentKind):
            raise TypeError("judgment uses an invalid enum")
        object.__setattr__(
            self,
            "record_id",
            stable_id(
                "layout-reading-order-normalized-replica-judgment",
                self.normalized_replica_evidence_id,
                self.candidate_order_id,
                self.covered_elements.sequence_id,
                (
                    None
                    if self.claimed_order is None
                    else self.claimed_order.sequence_id
                ),
                self.judgment,
            ),
        )

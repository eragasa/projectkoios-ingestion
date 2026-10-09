"""Immutable request for pure replicated reading-order evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.reading.order.candidate import (
    LayoutReadingOrderCandidate,
)

from .limits import (
    MAX_LAYOUT_READING_ORDER_EVALUATION_RELATIONS,
    MAX_LAYOUT_READING_ORDER_EVIDENCE_ID_CHARACTERS,
)
from .slot import LayoutReadingOrderReplicaJudgmentSlotInventory


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderEvaluationRequest(DataObjectActionRequest):
    """Bind one candidate, one opaque Search bundle, and declared replicas."""

    CONTRACT_NAME: ClassVar[str] = "layout-reading-order-evaluation-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    candidate: LayoutReadingOrderCandidate
    search_evidence_id: str
    replica_slots: LayoutReadingOrderReplicaJudgmentSlotInventory
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.candidate) is not LayoutReadingOrderCandidate:
            raise TypeError("candidate must be LayoutReadingOrderCandidate")
        if len(self.candidate) < 2:
            raise ValueError(
                "evaluation candidate requires at least two elements"
            )
        if (
            not isinstance(self.search_evidence_id, str)
            or not self.search_evidence_id.strip()
        ):
            raise ValueError("search_evidence_id must be non-empty")
        if (
            len(self.search_evidence_id)
            > MAX_LAYOUT_READING_ORDER_EVIDENCE_ID_CHARACTERS
        ):
            raise ValueError("search_evidence_id exceeds implementation limit")
        if any(ord(character) < 32 for character in self.search_evidence_id):
            raise ValueError("search_evidence_id contains control characters")
        if (
            type(self.replica_slots)
            is not LayoutReadingOrderReplicaJudgmentSlotInventory
        ):
            raise TypeError("replica_slots must be a replica slot inventory")
        element_count = len(self.candidate)
        maximum_relation_count = (
            len(self.replica_slots) * element_count * (element_count - 1) // 2
        )
        if (
            maximum_relation_count
            > MAX_LAYOUT_READING_ORDER_EVALUATION_RELATIONS
        ):
            raise ValueError("evaluation relation budget exceeded")
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.candidate.candidate_id,
                self.search_evidence_id,
                self.replica_slots.inventory_id,
            ),
        )

    @property
    def candidate_order_id(self) -> str:
        """Expose the exact single candidate identity bound by the request."""
        return self.candidate.candidate_id

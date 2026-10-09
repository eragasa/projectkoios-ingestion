"""Deterministic escalation reasons for reading-order evaluation."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from projectkoios.ingestion.identity import stable_id


class LayoutReadingOrderEvaluationEscalationReason(StrEnum):
    """Closed reasons that evaluation cannot stop without escalation."""

    TOO_FEW_DISTINCT_VALID_REPLICAS = "too_few_distinct_valid_replicas"
    MISSING_EVIDENCE = "missing_evidence"
    MALFORMED_EVIDENCE = "malformed_evidence"
    INCOMPLETE_COVERAGE = "incomplete_coverage"
    UNRESOLVED_JUDGMENT = "unresolved_judgment"
    REPLICA_DISAGREEMENT = "replica_disagreement"
    CANDIDATE_DISPUTED = "candidate_disputed"


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderEvaluationEscalationReasonInventory:
    """Own sorted unique escalation reasons."""

    _reasons: tuple[LayoutReadingOrderEvaluationEscalationReason, ...] = field(
        repr=True
    )
    inventory_id: str = field(init=False)

    def __init__(
        self, *reasons: LayoutReadingOrderEvaluationEscalationReason
    ) -> None:
        values = tuple(reasons)
        if any(
            not isinstance(reason, LayoutReadingOrderEvaluationEscalationReason)
            for reason in values
        ):
            raise TypeError("escalation reason uses an invalid enum")
        if (
            len(values) != len(set(values))
            or tuple(sorted(values, key=str)) != values
        ):
            raise ValueError("escalation reasons must be sorted and unique")
        object.__setattr__(self, "_reasons", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "layout-reading-order-evaluation-escalation-reasons", values
            ),
        )

    def __iter__(
        self,
    ) -> Iterator[LayoutReadingOrderEvaluationEscalationReason]:
        return iter(self._reasons)

    def __len__(self) -> int:
        return len(self._reasons)

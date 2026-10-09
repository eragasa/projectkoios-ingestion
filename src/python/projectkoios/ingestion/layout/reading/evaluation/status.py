"""Independent aggregate dimensions for reading-order evaluation."""

from enum import StrEnum


class LayoutReadingOrderReplicaAgreement(StrEnum):
    """Agreement among valid normalized replicas, not candidate correctness."""

    EXACT_AGREEMENT = "exact_agreement"
    CONSISTENT_PARTIAL = "consistent_partial"
    DISAGREEMENT = "disagreement"
    NOT_EVALUABLE = "not_evaluable"


class LayoutReadingOrderAggregateCoverage(StrEnum):
    """Coverage across all declared replica slots."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    NONE = "none"

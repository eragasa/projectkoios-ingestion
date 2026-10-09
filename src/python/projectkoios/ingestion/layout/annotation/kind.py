"""Layout annotation outcome and failure taxonomies."""

from enum import StrEnum


class LayoutAnnotationOutcome(StrEnum):
    """Observation recorded without granting publication authority."""

    NO_FAILURE_OBSERVED = "no_failure_observed"
    FAILURE_OBSERVED = "failure_observed"
    CORRECTION_PROPOSED = "correction_proposed"


class LayoutFailureKind(StrEnum):
    """Failure observed in baseline or proposal evidence."""

    MISSED_REGION = "missed_region"
    FALSE_REGION = "false_region"
    WRONG_REGION_KIND = "wrong_region_kind"
    MERGED_REGIONS = "merged_regions"
    SPLIT_REGION = "split_region"
    BLOCK_ASSIGNMENT = "block_assignment"
    READING_ORDER = "reading_order"
    BASELINE_GEOMETRY = "baseline_geometry"
    OTHER = "other"

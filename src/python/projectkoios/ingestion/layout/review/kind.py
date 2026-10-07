"""Deterministic layout review reason taxonomy."""

from enum import StrEnum


class LayoutReviewReason(StrEnum):
    """Deterministic reason that one page merits layout review."""

    BASELINE_AMBIGUOUS = "baseline_ambiguous"
    BASELINE_WARNING = "baseline_warning"
    INVALID_BLOCK_GEOMETRY = "invalid_block_geometry"
    NO_REGION_PROPOSALS = "no_region_proposals"
    INCOMPLETE_REGION_COVERAGE = "incomplete_region_coverage"
    CONFLICTING_REGION_KINDS = "conflicting_region_kinds"

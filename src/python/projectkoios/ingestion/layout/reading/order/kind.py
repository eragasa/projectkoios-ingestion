"""Reading-order direction, outcome, and escalation taxonomies."""

from enum import StrEnum


class LayoutReadingDirection(StrEnum):
    """Configured horizontal reading direction."""

    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"


class LayoutReadingOrderStatus(StrEnum):
    """Deterministic resolver outcome."""

    RESOLVED = "resolved"
    ESCALATION_REQUIRED = "escalation_required"


class LayoutReadingOrderReason(StrEnum):
    """Closed reasons that deterministic resolution cannot be admitted."""

    CANDIDATE_INCOMPLETE = "candidate_incomplete"
    CANDIDATE_UNKNOWN_REGION = "candidate_unknown_region"
    UNASSIGNED_NATIVE_BLOCK = "unassigned_native_block"
    UNKNOWN_NATIVE_BLOCK = "unknown_native_block"
    DUPLICATE_NATIVE_BLOCK_ASSIGNMENT = "duplicate_native_block_assignment"
    NATIVE_BLOCK_REGION_CONFLICT = "native_block_region_conflict"
    UNSUPPORTED_REGION_KIND = "unsupported_region_kind"
    CAPTION_ASSOCIATION_REQUIRED = "caption_association_required"
    FOOTNOTE_ASSOCIATION_REQUIRED = "footnote_association_required"
    OVERLAPPING_REGIONS = "overlapping_regions"
    HEADER_POSITION_CONFLICT = "header_position_conflict"
    FOOTER_POSITION_CONFLICT = "footer_position_conflict"
    SPANNING_REGION_AMBIGUOUS = "spanning_region_ambiguous"
    COLUMN_ORDER_AMBIGUOUS = "column_order_ambiguous"
    NATIVE_BLOCK_ORDER_AMBIGUOUS = "native_block_order_ambiguous"
    CANDIDATE_GEOMETRY_DISAGREEMENT = "candidate_geometry_disagreement"

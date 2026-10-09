"""Closed detector admission and escalation vocabularies."""

from enum import StrEnum


class CocoLayoutDetectorGateStatus(StrEnum):
    """State whether detector evidence may enter deterministic finalization."""

    ADMITTED = "admitted"
    ESCALATION_REQUIRED = "escalation_required"


class CocoLayoutDetectorGateReason(StrEnum):
    """Deterministic reasons detector evidence requires escalation."""

    DETERMINISTIC_LAYOUT_REVIEW_REQUIRED = (
        "deterministic_layout_review_required"
    )
    INSUFFICIENT_ACCEPTED_DETECTIONS = "insufficient_accepted_detections"
    LIMITATION_BOUND_EXCEEDED = "limitation_bound_exceeded"
    UNSUPPORTED_LABEL_OBSERVED = "unsupported_label_observed"

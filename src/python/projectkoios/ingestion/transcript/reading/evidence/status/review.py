"""Closed reading evidence review states."""

from enum import StrEnum


class ReadingReviewStatus(StrEnum):
    """Evidence-local review state, distinct from Workflow approval."""

    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

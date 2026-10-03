"""Equation publication inventory statuses."""

from enum import StrEnum


class EquationPublicationInventoryStatus(StrEnum):
    """Completeness of the recognition/index publication pair."""

    NONE = "none"
    COMPLETE_PAIR = "complete_pair"
    PARTIAL = "partial"

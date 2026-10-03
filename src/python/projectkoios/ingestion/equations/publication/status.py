"""Equation publication inventory statuses."""

from enum import StrEnum


class EquationPublicationInventoryStatus(StrEnum):
    """Completeness of recognition/index/derivation publication evidence."""

    NONE = "none"
    COMPLETE_SET = "complete_set"
    LEGACY_PAIR = "legacy_pair"
    PARTIAL = "partial"

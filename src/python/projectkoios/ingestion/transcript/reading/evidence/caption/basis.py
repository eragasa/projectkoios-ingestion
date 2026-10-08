"""Closed canonical caption selection bases."""

from enum import StrEnum


class ReadingCaptionSelectionBasis(StrEnum):
    """Deterministic rule used to select one exact caption."""

    UNIQUE_NORMALIZED_ASSOCIATION = "unique_normalized_association"

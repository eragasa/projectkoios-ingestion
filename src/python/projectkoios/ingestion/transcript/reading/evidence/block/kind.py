"""Closed canonical reading block kinds."""

from enum import StrEnum


class ReadingEvidenceBlockKind(StrEnum):
    """Semantic kinds admitted to canonical reading order."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    FIGURE = "figure"
    TABLE = "table"
    EQUATION = "equation"

"""Closed structured reading-item kinds."""

from enum import StrEnum


class ReadingStructuredItemKind(StrEnum):
    """Closed structured reading-item grammar."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    FIGURE = "figure"
    TABLE = "table"
    EQUATION = "equation"

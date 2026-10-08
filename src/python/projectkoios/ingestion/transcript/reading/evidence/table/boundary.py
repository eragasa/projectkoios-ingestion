"""Closed reading table boundary kinds."""

from enum import StrEnum


class ReadingTableBoundaryKind(StrEnum):
    """Observed table boundary structure."""

    RULED = "ruled"
    UNRULED = "unruled"
    MIXED = "mixed"

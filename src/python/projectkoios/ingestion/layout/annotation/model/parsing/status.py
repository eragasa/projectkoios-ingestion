"""Closed model-response parsing status."""

from enum import StrEnum


class LayoutModelResponseParsingStatus(StrEnum):
    """Closed parsing outcome."""

    PARSED = "parsed"
    REJECTED = "rejected"

"""Closed dispositions for a current-publication read."""

from enum import StrEnum


class PageProjectionPublicationReadDisposition(StrEnum):
    """State observed under one publication subject lock."""

    ABSENT = "absent"
    CURRENT = "current"

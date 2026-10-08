"""Closed mechanical reference page-location status."""

from enum import StrEnum


class ReferencePageLocatorStatus(StrEnum):
    """Mechanical whole-token phrase-match status."""

    MATCH = "match"
    NO_MATCH = "no_match"

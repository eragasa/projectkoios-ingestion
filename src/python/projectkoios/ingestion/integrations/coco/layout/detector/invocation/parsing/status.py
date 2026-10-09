"""Closed local detector output parsing outcomes."""

from enum import StrEnum


class CocoLayoutDetectorOutputParsingStatus(StrEnum):
    """State whether exact detector output was strictly reconstructed."""

    VALID = "valid"
    INVALID = "invalid"
    INVOCATION_FAILED = "invocation_failed"

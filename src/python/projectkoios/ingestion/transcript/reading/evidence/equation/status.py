"""Closed equation recognition states."""

from enum import StrEnum


class ReadingEquationRecognitionStatus(StrEnum):
    """Vendor-neutral equation recognition state."""

    NOT_REQUESTED = "not_requested"
    DEFERRED = "deferred"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

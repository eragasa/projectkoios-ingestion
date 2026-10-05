"""Status of one typed extraction action outcome."""

from __future__ import annotations

from enum import StrEnum


class ExtractionActionStatus(StrEnum):
    """Terminal status returned by one bounded owner action."""

    COMPLETED = "completed"
    FAILED = "failed"

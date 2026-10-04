"""OCRResultStatus OCR domain object."""

from __future__ import annotations

from enum import StrEnum


class OCRResultStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"

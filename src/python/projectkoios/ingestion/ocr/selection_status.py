"""OCRSelectionStatus OCR domain object."""

from __future__ import annotations

from enum import StrEnum


class OCRSelectionStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"

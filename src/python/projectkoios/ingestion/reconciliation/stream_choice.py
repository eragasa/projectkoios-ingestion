"""OCRReconciliationStreamChoice reconciliation domain object."""

from __future__ import annotations

from enum import StrEnum


class OCRReconciliationStreamChoice(StrEnum):
    NATIVE = "native"
    OCR = "ocr"
    PROPOSED_MERGED = "proposed_merged"

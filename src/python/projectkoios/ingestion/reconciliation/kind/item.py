"""OCRReconciledItemKind reconciliation domain object."""

from __future__ import annotations

from enum import StrEnum


class OCRReconciledItemKind(StrEnum):
    DUPLICATE = "duplicate"
    DISAGREEMENT = "disagreement"
    NATIVE_ONLY = "native_only"
    OCR_ONLY = "ocr_only"

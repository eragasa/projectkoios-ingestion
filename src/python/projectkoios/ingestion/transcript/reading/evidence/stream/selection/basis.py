"""Closed reading text stream selection bases."""

from enum import StrEnum


class ReadingTextSelectionBasis(StrEnum):
    """Exact basis for one selected page stream."""

    NATIVE_EXACT = "native_exact"
    OCR_COMPOSITION_EXACT = "ocr_composition_exact"

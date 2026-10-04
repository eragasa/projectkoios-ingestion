"""OCROutputMode OCR domain object."""

from __future__ import annotations

from enum import StrEnum


class OCROutputMode(StrEnum):
    """The independently retained OCR evidence requested from an adapter."""

    TOKENS = "tokens"
    LINES = "lines"
    TOKENS_AND_LINES = "tokens_and_lines"

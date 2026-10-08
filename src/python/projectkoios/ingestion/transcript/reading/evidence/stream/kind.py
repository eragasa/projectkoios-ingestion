"""Closed reading text stream kinds."""

from enum import StrEnum


class ReadingTextStreamKind(StrEnum):
    """Exact producer origin for retained page text."""

    NATIVE = "native"
    OCR = "ocr"

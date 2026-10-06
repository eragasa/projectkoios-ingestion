"""OCRFailureKind OCR domain object."""

from __future__ import annotations

from enum import StrEnum


class OCRFailureKind(StrEnum):
    """Engine-neutral categories for a selection that did not complete."""

    INPUT_REJECTED = "input_rejected"
    RESOURCE_LIMIT = "resource_limit"
    PROCESSOR_UNAVAILABLE = "processor_unavailable"
    PROCESSOR_ERROR = "processor_error"
    UNSUPPORTED_LANGUAGE = "unsupported_language"
    OUTPUT_INVALID = "output_invalid"

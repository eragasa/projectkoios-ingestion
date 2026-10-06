"""Figure-relevance failure kinds."""

from __future__ import annotations

from enum import StrEnum


class FigureRelevanceFailureKind(StrEnum):
    INPUT_REJECTED = "input_rejected"
    STALE_INPUT = "stale_input"
    RESOURCE_LIMIT = "resource_limit"
    PROCESSOR_UNAVAILABLE = "processor_unavailable"
    PROCESSOR_ERROR = "processor_error"
    OUTPUT_INVALID = "output_invalid"
    OUTPUT_INCOMPLETE = "output_incomplete"

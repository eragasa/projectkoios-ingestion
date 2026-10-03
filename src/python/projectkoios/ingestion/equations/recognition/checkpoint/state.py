"""Equation-recognition work states."""

from enum import StrEnum


class EquationRecognitionWorkState(StrEnum):
    """Durable state of one recognition work item."""

    PENDING = "pending"
    NOT_REQUESTED = "not_requested"
    COMPLETE = "complete"
    FAILED = "failed"

"""Equation-recognition proposal statuses."""

from enum import StrEnum


class EquationRecognitionStatus(StrEnum):
    """Automated proposal status without acceptance semantics."""

    PROPOSED = "proposed"
    FAILED = "failed"
    NOT_REQUESTED = "not_requested"

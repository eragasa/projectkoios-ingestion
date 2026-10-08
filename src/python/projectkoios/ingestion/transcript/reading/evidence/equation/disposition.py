"""Closed equation selection dispositions."""

from enum import StrEnum


class ReadingEquationSelectionDisposition(StrEnum):
    """Primary, auxiliary, or rejected equation selection."""

    PRIMARY = "primary"
    AUXILIARY = "auxiliary"
    REJECTED = "rejected"

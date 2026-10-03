"""Equation derivation transition outcomes."""

from enum import StrEnum


class EquationDerivationTransitionStatus(StrEnum):
    """Terminal outcome of one attempted representation transition."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"

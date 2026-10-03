"""Equation index tiers."""

from enum import StrEnum


class EquationIndexTier(StrEnum):
    """Deterministic promotion tier for equation retrieval evidence."""

    PRIMARY = "primary"
    AUXILIARY = "auxiliary"
    REJECTED = "rejected"

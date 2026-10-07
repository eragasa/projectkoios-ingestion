"""Shared validation for immutable layout-domain values."""

from __future__ import annotations

import math

from projectkoios.ingestion.layout.limits.definition import (
    MAX_LAYOUT_COORDINATE_MAGNITUDE,
    MAX_LAYOUT_IDENTITY_FIELD_CHARACTERS,
)
from projectkoios.ingestion.layout.limits.error import LayoutLimitError


class LayoutValueValidation:
    """Validate and normalize values shared by layout-domain contracts."""

    __slots__ = ()

    @staticmethod
    def require_text(
        name: str,
        value: object,
        *,
        max_characters: int = MAX_LAYOUT_IDENTITY_FIELD_CHARACTERS,
    ) -> str:
        """Return one bounded non-empty string without changing its bytes."""
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string")
        if len(value) > max_characters:
            raise LayoutLimitError(
                f"{name} exceeds implementation character limit "
                f"({max_characters})"
            )
        return value

    @staticmethod
    def require_positive_integer(
        name: str,
        value: object,
        *,
        maximum: int | None = None,
    ) -> int:
        """Return one bounded positive non-boolean integer."""
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        if maximum is not None and value > maximum:
            raise LayoutLimitError(
                f"{name} exceeds implementation maximum ({maximum})"
            )
        return value

    @staticmethod
    def require_nonnegative_integer(
        name: str,
        value: object,
        *,
        maximum: int | None = None,
    ) -> int:
        """Return one bounded non-negative non-boolean integer."""
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
        if maximum is not None and value > maximum:
            raise LayoutLimitError(
                f"{name} exceeds implementation maximum ({maximum})"
            )
        return value

    @staticmethod
    def require_number(name: str, value: object) -> float:
        """Return one finite bounded number with negative zero normalized."""
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{name} must be a finite number")
        normalized = float(value)
        if not math.isfinite(normalized):
            raise ValueError(f"{name} must be a finite number")
        if abs(normalized) > MAX_LAYOUT_COORDINATE_MAGNITUDE:
            raise LayoutLimitError(
                f"{name} exceeds coordinate magnitude limit"
            )
        return 0.0 if normalized == 0.0 else normalized

    @staticmethod
    def require_ratio(name: str, value: object) -> float:
        """Return one finite ratio in the inclusive unit interval."""
        normalized = LayoutValueValidation.require_number(name, value)
        if not 0.0 <= normalized <= 1.0:
            raise ValueError(f"{name} must be between zero and one")
        return normalized

    @staticmethod
    def require_box(
        name: str, value: object
    ) -> tuple[float, float, float, float]:
        """Return one finite positive-area axis-aligned box."""
        if not isinstance(value, tuple) or len(value) != 4:
            raise ValueError(f"{name} must be a four-value tuple")
        normalized = tuple(
            LayoutValueValidation.require_number(
                f"{name} coordinate", coordinate
            )
            for coordinate in value
        )
        box = (
            normalized[0],
            normalized[1],
            normalized[2],
            normalized[3],
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            raise ValueError(f"{name} must have positive area")
        return box

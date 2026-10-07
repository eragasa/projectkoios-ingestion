"""Shared validation for immutable layout-domain values."""

from __future__ import annotations

import math

from projectkoios.ingestion.layout.limits.definition import (
    MAX_LAYOUT_EVIDENCE_ITEMS,
)
from projectkoios.ingestion.layout.limits.error import LayoutLimitError
from projectkoios.ingestion.models import Metadata


class LayoutValueValidation:
    """Validate and normalize values shared by layout-domain contracts."""

    __slots__ = ()

    @staticmethod
    def require_text(name: str, value: object) -> str:
        """Return one non-empty string without changing its bytes."""
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string")
        return value

    @staticmethod
    def require_positive_integer(name: str, value: object) -> int:
        """Return one positive non-boolean integer."""
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return value

    @staticmethod
    def require_ratio(name: str, value: object) -> float:
        """Return one finite ratio in the inclusive unit interval."""
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{name} must be a finite ratio")
        normalized = float(value)
        if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise ValueError(f"{name} must be between zero and one")
        return normalized

    @staticmethod
    def require_box(
        name: str, value: object
    ) -> tuple[float, float, float, float]:
        """Return one finite positive-area axis-aligned box."""
        if not isinstance(value, tuple) or len(value) != 4:
            raise ValueError(f"{name} must be a four-value tuple")
        normalized: list[float] = []
        for coordinate in value:
            if isinstance(coordinate, bool) or not isinstance(
                coordinate, int | float
            ):
                raise ValueError(f"{name} coordinates must be finite numbers")
            number = float(coordinate)
            if not math.isfinite(number):
                raise ValueError(f"{name} coordinates must be finite numbers")
            normalized.append(number)
        box = (
            normalized[0],
            normalized[1],
            normalized[2],
            normalized[3],
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            raise ValueError(f"{name} must have positive area")
        return box

    @staticmethod
    def normalize_metadata(value: object) -> Metadata:
        """Return deterministic unique string evidence pairs."""
        if not isinstance(value, tuple):
            raise TypeError("evidence must be a tuple")
        normalized: list[tuple[str, str]] = []
        for item in value:
            if not isinstance(item, tuple) or len(item) != 2:
                raise TypeError("evidence items must be two-value tuples")
            key = LayoutValueValidation.require_text("evidence key", item[0])
            content = LayoutValueValidation.require_text(
                "evidence value", item[1]
            )
            normalized.append((key, content))
        if len(normalized) > MAX_LAYOUT_EVIDENCE_ITEMS:
            raise LayoutLimitError("evidence exceeds implementation maximum")
        if len({key for key, _ in normalized}) != len(normalized):
            raise ValueError("evidence keys must be unique")
        return tuple(sorted(normalized))

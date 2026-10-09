"""Typed value checks shared by COCO layout JSON contracts."""

from __future__ import annotations

from projectkoios.ingestion.json.value import JsonValue


class CocoLayoutJsonValue:
    """Own exact field and primitive checks for COCO layout JSON."""

    __slots__ = ()

    @staticmethod
    def require_object(
        value: JsonValue,
        *,
        field: str,
        expected_fields: frozenset[str],
    ) -> dict[str, JsonValue]:
        """Require one object with exactly the declared field set."""
        if not isinstance(value, dict):
            raise ValueError(f"{field} must be an object")
        actual = set(value)
        missing = expected_fields - actual
        unknown = actual - expected_fields
        if missing:
            raise ValueError(f"{field} is missing fields: {sorted(missing)}")
        if unknown:
            raise ValueError(f"{field} has unknown fields: {sorted(unknown)}")
        return value

    @staticmethod
    def require_array(value: JsonValue, *, field: str) -> list[JsonValue]:
        """Require one JSON array."""
        if not isinstance(value, list):
            raise ValueError(f"{field} must be an array")
        return value

    @staticmethod
    def require_string(value: JsonValue, *, field: str) -> str:
        """Require one non-empty JSON string."""
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} must be a non-empty string")
        return value

    @staticmethod
    def require_integer(value: JsonValue, *, field: str) -> int:
        """Require one non-negative JSON integer excluding booleans."""
        if type(value) is not int or value < 0:
            raise ValueError(f"{field} must be a non-negative integer")
        return value

    @staticmethod
    def require_number(value: JsonValue, *, field: str) -> float:
        """Require one finite JSON number excluding booleans."""
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{field} must be a number")
        return float(value)

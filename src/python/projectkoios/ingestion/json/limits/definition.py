"""Validated resource bounds for JSON operations."""

from __future__ import annotations

from dataclasses import dataclass

MAX_JSON_UTF8_BYTES = 1_000_000_000
MAX_JSON_CONTAINER_DEPTH = 512
MAX_JSON_ITEMS = 100_000_000
MAX_JSON_STRING_BYTES = 1_000_000_000
MAX_JSON_TOTAL_STRING_BYTES = 1_000_000_000
MAX_JSON_NUMBER_CHARACTERS = 4_096


@dataclass(frozen=True, slots=True)
class JsonLimits:
    """Explicit byte and structural bounds for one JSON boundary."""

    maximum_utf8_bytes: int
    maximum_container_depth: int
    maximum_items: int
    maximum_string_bytes: int
    maximum_total_string_bytes: int
    maximum_number_characters: int

    def __post_init__(self) -> None:
        for name, hard_maximum in (
            ("maximum_utf8_bytes", MAX_JSON_UTF8_BYTES),
            ("maximum_container_depth", MAX_JSON_CONTAINER_DEPTH),
            ("maximum_items", MAX_JSON_ITEMS),
            ("maximum_string_bytes", MAX_JSON_STRING_BYTES),
            ("maximum_total_string_bytes", MAX_JSON_TOTAL_STRING_BYTES),
            ("maximum_number_characters", MAX_JSON_NUMBER_CHARACTERS),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            if value > hard_maximum:
                raise ValueError(f"{name} exceeds the JSON hard limit")
        if self.maximum_string_bytes > self.maximum_total_string_bytes:
            raise ValueError(
                "maximum_string_bytes cannot exceed maximum_total_string_bytes"
            )
        if self.maximum_total_string_bytes > self.maximum_utf8_bytes:
            raise ValueError(
                "maximum_total_string_bytes cannot exceed maximum_utf8_bytes"
            )

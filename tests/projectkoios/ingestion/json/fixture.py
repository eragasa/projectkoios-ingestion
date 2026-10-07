from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.json.limits.definition import JsonLimits


@dataclass(frozen=True)
class JsonFixture:
    """Own bounded JSON configurations used across focused tests."""

    def limits(
        self,
        *,
        maximum_utf8_bytes: int = 4_096,
        maximum_container_depth: int = 8,
        maximum_items: int = 128,
        maximum_string_bytes: int = 1_024,
        maximum_total_string_bytes: int = 2_048,
        maximum_number_characters: int = 32,
    ) -> JsonLimits:
        return JsonLimits(
            maximum_utf8_bytes=maximum_utf8_bytes,
            maximum_container_depth=maximum_container_depth,
            maximum_items=maximum_items,
            maximum_string_bytes=maximum_string_bytes,
            maximum_total_string_bytes=maximum_total_string_bytes,
            maximum_number_characters=maximum_number_characters,
        )

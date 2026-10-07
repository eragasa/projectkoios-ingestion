"""Canonical JSON serialization for immutable values and identity material."""

from __future__ import annotations

from typing import ClassVar

from projectkoios.ingestion.json.limits.definition import (
    MAX_JSON_CONTAINER_DEPTH,
    MAX_JSON_ITEMS,
    MAX_JSON_NUMBER_CHARACTERS,
    MAX_JSON_STRING_BYTES,
    MAX_JSON_TOTAL_STRING_BYTES,
    MAX_JSON_UTF8_BYTES,
    JsonLimits,
)
from projectkoios.ingestion.json.serializer import JsonSerializer
from projectkoios.ingestion.json.value import JsonValue, JsonValueProjector


class CanonicalJsonSerializer:
    """Project immutable values to compact sorted deterministic JSON."""

    __slots__ = ()

    limits: ClassVar[JsonLimits] = JsonLimits(
        maximum_utf8_bytes=MAX_JSON_UTF8_BYTES,
        maximum_container_depth=MAX_JSON_CONTAINER_DEPTH,
        maximum_items=MAX_JSON_ITEMS,
        maximum_string_bytes=MAX_JSON_STRING_BYTES,
        maximum_total_string_bytes=MAX_JSON_TOTAL_STRING_BYTES,
        maximum_number_characters=MAX_JSON_NUMBER_CHARACTERS,
    )
    projector: ClassVar[JsonValueProjector] = JsonValueProjector(
        limits,
        allow_non_finite=True,
    )
    serializer: ClassVar[JsonSerializer] = JsonSerializer(
        limits=limits,
        ensure_ascii=False,
        sort_keys=True,
        allow_non_finite=True,
        indent=None,
        separators=(",", ":"),
        terminal_newline=False,
    )

    @classmethod
    def project(cls, value: object) -> JsonValue:
        return cls.projector.project(value)

    @classmethod
    def project_object(cls, value: object) -> dict[str, JsonValue]:
        return cls.projector.project_object(value)

    @classmethod
    def serialize_text(cls, value: object) -> str:
        return cls.serializer.serialize_text(cls.project(value))

    @classmethod
    def serialize_bytes(cls, value: object) -> bytes:
        return cls.serializer.serialize_bytes(cls.project(value))

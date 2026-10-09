"""Shared bounded canonical mechanics for COCO layout JSON documents."""

from __future__ import annotations

from typing import ClassVar

from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_JSON_BYTES,
    MAX_COCO_LAYOUT_JSON_CONTAINER_DEPTH,
    MAX_COCO_LAYOUT_JSON_ITEMS,
    MAX_COCO_LAYOUT_JSON_NUMBER_CHARACTERS,
    MAX_COCO_LAYOUT_JSON_STRING_BYTES,
    MAX_COCO_LAYOUT_JSON_TOTAL_STRING_BYTES,
)
from projectkoios.ingestion.json.contract import JsonContract
from projectkoios.ingestion.json.limits.definition import JsonLimits
from projectkoios.ingestion.json.parser import JsonParser
from projectkoios.ingestion.json.serializer import JsonSerializer


class CocoLayoutJsonContract[RecordT](JsonContract[RecordT]):
    """Provide one fail-closed canonical JSON policy for every bundle member."""

    __slots__ = ()

    limits: ClassVar[JsonLimits] = JsonLimits(
        maximum_utf8_bytes=MAX_COCO_LAYOUT_JSON_BYTES,
        maximum_container_depth=MAX_COCO_LAYOUT_JSON_CONTAINER_DEPTH,
        maximum_items=MAX_COCO_LAYOUT_JSON_ITEMS,
        maximum_string_bytes=MAX_COCO_LAYOUT_JSON_STRING_BYTES,
        maximum_total_string_bytes=MAX_COCO_LAYOUT_JSON_TOTAL_STRING_BYTES,
        maximum_number_characters=MAX_COCO_LAYOUT_JSON_NUMBER_CHARACTERS,
    )
    parser_instance: ClassVar[JsonParser] = JsonParser(limits)
    serializer_instance: ClassVar[JsonSerializer] = JsonSerializer.canonical(
        limits=limits
    )

    @property
    def parser(self) -> JsonParser:
        return self.parser_instance

    @property
    def serializer(self) -> JsonSerializer:
        return self.serializer_instance

    @property
    def requires_canonical_replay(self) -> bool:
        return True

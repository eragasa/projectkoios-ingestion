"""Generic typed JSON document boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.json.parser import JsonParser
from projectkoios.ingestion.json.serializer import JsonSerializer
from projectkoios.ingestion.json.value import JsonValue


class JsonContract[JsonRecordT](ABC):
    """Compose bounded JSON mechanics with typed record reconstruction."""

    __slots__ = ()

    @property
    @abstractmethod
    def parser(self) -> JsonParser:
        """Return the immutable parser for this document boundary."""

    @property
    @abstractmethod
    def serializer(self) -> JsonSerializer:
        """Return the immutable serializer for this document boundary."""

    @property
    def requires_canonical_replay(self) -> bool:
        return False

    @abstractmethod
    def to_json_value(self, value: JsonRecordT) -> JsonValue:
        """Project one typed record to its exact JSON value tree."""

    @abstractmethod
    def from_json_value(self, value: JsonValue) -> JsonRecordT:
        """Reconstruct one typed record from a validated JSON value tree."""

    def serialize_text(self, value: JsonRecordT) -> str:
        return self.serializer.serialize_text(self.to_json_value(value))

    def serialize_bytes(self, value: JsonRecordT) -> bytes:
        return self.serializer.serialize_bytes(self.to_json_value(value))

    def parse_text(self, content: str) -> JsonRecordT:
        value = self.parser.parse_text(content)
        record = self.from_json_value(value)
        if (
            self.requires_canonical_replay
            and self.serialize_text(record) != content
        ):
            raise JsonParseError("JSON content is not canonical serialization")
        return record

    def parse_bytes(self, content: bytes) -> JsonRecordT:
        value = self.parser.parse_bytes(content)
        record = self.from_json_value(value)
        if (
            self.requires_canonical_replay
            and self.serialize_bytes(record) != content
        ):
            raise JsonParseError("JSON content is not canonical serialization")
        return record

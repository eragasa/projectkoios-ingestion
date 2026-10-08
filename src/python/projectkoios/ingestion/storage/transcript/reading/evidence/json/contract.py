"""Reversible typed JSON boundary for current reading-evidence storage."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, ClassVar, cast

from projectkoios.ingestion.json.contract import JsonContract
from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.json.limits.definition import JsonLimits
from projectkoios.ingestion.json.parser import JsonParser
from projectkoios.ingestion.json.serializer import JsonSerializer
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.storage.transcript.reading.evidence.json.registry import (  # noqa: E501
    ENUM_REGISTRY,
    ENUM_TAGS,
    SEQUENCE_INVENTORIES,
    TYPE_REGISTRY,
    TYPE_TAGS,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.evidence import (  # noqa: E501
    ReadingPageTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.inventory import (  # noqa: E501
    ReadingTextStreamEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.basis import (  # noqa: E501
    ReadingTextSelectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.definition import (  # noqa: E501
    ReadingTextSelection,
)


class ReadingEvidenceStorageJsonContract(JsonContract[object]):
    """Encode and reconstruct the explicit current storage value registry."""

    __slots__ = ()

    limits: ClassVar[JsonLimits] = JsonLimits(
        maximum_utf8_bytes=4_194_304,
        maximum_container_depth=128,
        maximum_items=1_000_000,
        maximum_string_bytes=4_000_000,
        maximum_total_string_bytes=4_194_304,
        maximum_number_characters=256,
    )
    _parser: ClassVar[JsonParser] = JsonParser(limits)
    _serializer: ClassVar[JsonSerializer] = JsonSerializer.canonical(
        limits=limits
    )

    @property
    def parser(self) -> JsonParser:
        return self._parser

    @property
    def serializer(self) -> JsonSerializer:
        return self._serializer

    @property
    def requires_canonical_replay(self) -> bool:
        return True

    def to_json_value(self, value: object) -> JsonValue:
        """Encode one admitted current-schema value."""
        if type(value) is ReadingPageTextProducerEvidence:
            return self._encode_page_text(value)
        if value is None or type(value) in (bool, int, float):
            return cast(JsonValue, value)
        if isinstance(value, str) and not isinstance(value, Enum):
            return str(value)
        if isinstance(value, Enum):
            enum_type = type(value)
            try:
                tag = ENUM_TAGS[enum_type]
            except KeyError as error:
                raise TypeError("enum type is not registered") from error
            return {"$enum": tag, "value": cast(str, value.value)}
        if type(value) is tuple:
            return [self.to_json_value(item) for item in value]
        value_type = type(value)
        try:
            tag = TYPE_TAGS[value_type]
        except KeyError as error:
            raise TypeError("value type is not registered") from error
        if not is_dataclass(value):
            raise TypeError("registered value is not a dataclass")
        initial: dict[str, JsonValue] = {}
        derived: dict[str, JsonValue] = {}
        for item in fields(value):
            name = item.name.removeprefix("_")
            target = initial if item.init else derived
            target[name] = self.to_json_value(getattr(value, item.name))
        return {"$type": tag, "fields": initial, "derived": derived}

    def from_json_value(self, value: JsonValue) -> object:
        """Strictly reconstruct one admitted current-schema value."""
        if value is None or type(value) in (bool, int, float, str):
            return value
        if type(value) is list:
            return tuple(self.from_json_value(item) for item in value)
        root = self._object(value, "typed value")
        if "$enum" in root:
            self._keys(root, {"$enum", "value"})
            tag = self._string(root["$enum"], "enum tag")
            member = self._string(root["value"], "enum value")
            try:
                return ENUM_REGISTRY[tag](member)
            except (KeyError, ValueError) as error:
                raise JsonParseError("typed JSON enum is unknown") from error
        self._keys(root, {"$type", "fields", "derived"})
        tag = self._string(root["$type"], "type tag")
        if tag == "page_text_producer":
            return self._decode_page_text(root)
        try:
            value_type = TYPE_REGISTRY[tag]
        except KeyError as error:
            raise JsonParseError("typed JSON type is unknown") from error
        definitions = tuple(fields(value_type))
        raw_initial = self._object(root["fields"], "fields")
        raw_derived = self._object(root["derived"], "derived")
        self._keys(
            raw_initial,
            {item.name.removeprefix("_") for item in definitions if item.init},
        )
        self._keys(
            raw_derived,
            {
                item.name.removeprefix("_")
                for item in definitions
                if not item.init
            },
        )
        decoded = {
            item.name.removeprefix("_"): self.from_json_value(
                raw_initial[item.name.removeprefix("_")]
            )
            for item in definitions
            if item.init
        }
        instance = self._construct(value_type, decoded)
        for item in definitions:
            if item.init:
                continue
            name = item.name.removeprefix("_")
            if getattr(instance, item.name) != self.from_json_value(
                raw_derived[name]
            ):
                raise JsonParseError(
                    f"stored derived field differs: {tag}.{name}"
                )
        return instance

    def decode_as(self, value: JsonValue, expected_type: type[Any]) -> Any:
        """Decode and require one exact result type."""
        decoded = self.from_json_value(value)
        if type(decoded) is not expected_type:
            raise JsonParseError("typed JSON value has the wrong type")
        return decoded

    def _construct(
        self, value_type: type[Any], values: dict[str, object]
    ) -> Any:
        if value_type is ReadingEvidenceIdentityInventory:
            identities = values["identities"]
            if type(identities) is not tuple:
                raise JsonParseError("identity inventory must be an array")
            kind = values["kind"]
            if not isinstance(kind, ReadingEvidenceIdentityKind):
                raise JsonParseError("identity inventory kind is invalid")
            return ReadingEvidenceIdentityInventory(kind, *identities)
        if value_type in SEQUENCE_INVENTORIES:
            sequences = tuple(
                (name, value)
                for name, value in values.items()
                if type(value) is tuple
            )
            if len(sequences) != 1:
                raise JsonParseError("inventory schema is invalid")
            sequence_name, items = sequences[0]
            instance = value_type(*items)
            definitions = {
                item.name.removeprefix("_"): item.name
                for item in fields(value_type)
            }
            for name, value in values.items():
                if name == sequence_name:
                    continue
                if getattr(instance, definitions[name]) != value:
                    raise JsonParseError("inventory derived value differs")
            return instance
        return value_type(**values)

    def _encode_page_text(
        self, value: ReadingPageTextProducerEvidence
    ) -> JsonValue:
        selection = value.selection
        return {
            "$type": "page_text_producer",
            "fields": {
                "streams": self.to_json_value(value.streams),
                "selection": {
                    "selected_stream_id": self.to_json_value(
                        selection.selected_stream_id
                    ),
                    "basis": self.to_json_value(selection.basis),
                },
                "producer_id": self.to_json_value(value.producer_id),
                "producer_version": value.producer_version,
                "review_status": self.to_json_value(value.review_status),
            },
            "derived": {
                "selection_id": self.to_json_value(selection.selection_id),
                "selection_page_location": self.to_json_value(
                    selection.page_location
                ),
                "selection_producer_id": self.to_json_value(
                    selection.producer_id
                ),
                "selection_composition_id": self.to_json_value(
                    selection.composition_id
                ),
                "record_id": self.to_json_value(value.record_id),
            },
        }

    def _decode_page_text(
        self, root: dict[str, JsonValue]
    ) -> ReadingPageTextProducerEvidence:
        initial = self._object(root["fields"], "page fields")
        derived = self._object(root["derived"], "page derived fields")
        self._keys(
            initial,
            {
                "streams",
                "selection",
                "producer_id",
                "producer_version",
                "review_status",
            },
        )
        self._keys(
            derived,
            {
                "selection_id",
                "selection_page_location",
                "selection_producer_id",
                "selection_composition_id",
                "record_id",
            },
        )
        streams = self.decode_as(
            initial["streams"], ReadingTextStreamEvidenceInventory
        )
        raw_selection = self._object(initial["selection"], "selection")
        self._keys(raw_selection, {"selected_stream_id", "basis"})
        selection = ReadingTextSelection(
            streams=streams,
            selected_stream_id=self.decode_as(
                raw_selection["selected_stream_id"], ReadingEvidenceIdentity
            ),
            basis=self.decode_as(
                raw_selection["basis"], ReadingTextSelectionBasis
            ),
        )
        comparisons = {
            "selection_id": selection.selection_id,
            "selection_page_location": selection.page_location,
            "selection_producer_id": selection.producer_id,
            "selection_composition_id": selection.composition_id,
        }
        for name, actual in comparisons.items():
            if actual != self.from_json_value(derived[name]):
                raise JsonParseError(f"stored derived field differs: {name}")
        producer = ReadingPageTextProducerEvidence(
            streams=streams,
            selection=selection,
            producer_id=self.decode_as(
                initial["producer_id"], ReadingEvidenceIdentity
            ),
            producer_version=self._string(
                initial["producer_version"], "producer_version"
            ),
            review_status=self.decode_as(
                initial["review_status"], ReadingReviewStatus
            ),
        )
        if producer.record_id != self.from_json_value(derived["record_id"]):
            raise JsonParseError(
                "stored derived field differs: page_text.record_id"
            )
        return producer

    @staticmethod
    def _object(value: JsonValue, name: str) -> dict[str, JsonValue]:
        if type(value) is not dict:
            raise JsonParseError(f"{name} must be an object")
        return value

    @staticmethod
    def _string(value: JsonValue, name: str) -> str:
        if type(value) is not str:
            raise JsonParseError(f"{name} must be a string")
        return value

    @staticmethod
    def _keys(value: dict[str, JsonValue], expected: set[str]) -> None:
        if set(value) != expected:
            raise JsonParseError("typed JSON fields differ from current schema")

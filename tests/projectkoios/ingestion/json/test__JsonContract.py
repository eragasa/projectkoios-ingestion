from __future__ import annotations

from dataclasses import dataclass

import pytest
from projectkoios.ingestion.json.contract import JsonContract
from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.json.parser import JsonParser
from projectkoios.ingestion.json.serializer import JsonSerializer
from projectkoios.ingestion.json.value import JsonValue

from tests.projectkoios.ingestion.json.fixture import JsonFixture

FIXTURE = JsonFixture()


@dataclass(frozen=True)
class FixtureRecord:
    value: int


class FixtureJsonContract(JsonContract[FixtureRecord]):
    def __init__(self, *, canonical_replay: bool) -> None:
        limits = FIXTURE.limits()
        self._parser = JsonParser(limits)
        self._serializer = JsonSerializer.canonical(limits=limits)
        self._canonical_replay = canonical_replay

    @property
    def parser(self) -> JsonParser:
        return self._parser

    @property
    def serializer(self) -> JsonSerializer:
        return self._serializer

    @property
    def requires_canonical_replay(self) -> bool:
        return self._canonical_replay

    def to_json_value(self, value: FixtureRecord) -> JsonValue:
        if type(value) is not FixtureRecord:
            raise TypeError("value must be FixtureRecord")
        return {"value": value.value}

    def from_json_value(self, value: JsonValue) -> FixtureRecord:
        if not isinstance(value, dict) or set(value) != {"value"}:
            raise ValueError("fixture JSON shape is invalid")
        raw = value["value"]
        if type(raw) is not int:
            raise TypeError("value must be an integer")
        return FixtureRecord(raw)


def test__json_contract__round_trips_typed_text_and_bytes() -> None:
    contract = FixtureJsonContract(canonical_replay=False)
    record = FixtureRecord(7)

    assert contract.serialize_text(record) == '{"value":7}'
    assert contract.serialize_bytes(record) == b'{"value":7}'
    assert contract.parse_text('{ "value" : 7 }') == record
    assert contract.parse_bytes(b'{"value":7}') == record


def test__json_contract__optionally_requires_canonical_replay() -> None:
    contract = FixtureJsonContract(canonical_replay=True)

    assert contract.parse_text('{"value":7}') == FixtureRecord(7)
    with pytest.raises(JsonParseError, match="canonical"):
        contract.parse_text('{ "value" : 7 }')

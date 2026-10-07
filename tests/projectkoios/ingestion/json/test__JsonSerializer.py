from __future__ import annotations

import pytest
from projectkoios.ingestion.json.error import JsonSerializationError
from projectkoios.ingestion.json.limits.error import JsonLimitError
from projectkoios.ingestion.json.serializer import JsonSerializer

from tests.projectkoios.ingestion.json.fixture import JsonFixture

FIXTURE = JsonFixture()


def test__json_serializer__emits_exact_canonical_bytes() -> None:
    serializer = JsonSerializer.canonical(limits=FIXTURE.limits())

    text = serializer.serialize_text({"z": 1, "a": "é"})

    assert text == '{"a":"é","z":1}'
    assert serializer.serialize_bytes({"z": 1, "a": "é"}) == text.encode(
        "utf-8"
    )


def test__json_serializer__emits_exact_durable_pretty_bytes() -> None:
    serializer = JsonSerializer.durable_pretty(
        limits=FIXTURE.limits(),
        sort_keys=False,
    )

    assert serializer.serialize_text({"z": 1, "a": 2}) == (
        '{\n  "z": 1,\n  "a": 2\n}\n'
    )


def test__json_serializer__rejects_nonfinite_and_excessive_output() -> None:
    serializer = JsonSerializer.canonical(limits=FIXTURE.limits())
    with pytest.raises(JsonSerializationError, match="finite"):
        serializer.serialize_text(float("inf"))

    content = '"abc"'
    exact = JsonSerializer.canonical(
        limits=FIXTURE.limits(
            maximum_utf8_bytes=len(content),
            maximum_string_bytes=5,
            maximum_total_string_bytes=5,
        )
    )
    assert exact.serialize_text("abc") == content
    with pytest.raises(JsonLimitError, match="serialized"):
        exact.serialize_text("abcd")

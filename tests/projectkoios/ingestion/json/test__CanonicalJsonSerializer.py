from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pytest
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.json.error import JsonSerializationError


class FixtureKind(StrEnum):
    VALUE = "value"


@dataclass(frozen=True)
class FixtureRecord:
    text: str
    kind: FixtureKind
    path: Path
    payload: bytes


def test__canonical_json_serializer__preserves_exact_existing_profile() -> None:
    value = FixtureRecord(
        text="héllo",
        kind=FixtureKind.VALUE,
        path=Path("a/b"),
        payload=b"\x00\xff",
    )

    assert CanonicalJsonSerializer.serialize_text(value) == (
        '{"kind":"value","path":"a/b","payload":{"hex":"00ff"},"text":"héllo"}'
    )
    assert CanonicalJsonSerializer.serialize_bytes(value) == (
        CanonicalJsonSerializer.serialize_text(value).encode("utf-8")
    )


def test__canonical_json_serializer__preserves_legacy_nonfinite_bytes() -> None:
    projected = CanonicalJsonSerializer.project(float("nan"))

    assert isinstance(projected, float) and math.isnan(projected)
    assert CanonicalJsonSerializer.serialize_text({"value": projected}) == (
        '{"value":NaN}'
    )


def test__canonical_json_serializer__projects_object_roots() -> None:
    assert CanonicalJsonSerializer.project_object({"value": 1}) == {"value": 1}
    with pytest.raises(JsonSerializationError, match="root"):
        CanonicalJsonSerializer.project_object((1, 2))

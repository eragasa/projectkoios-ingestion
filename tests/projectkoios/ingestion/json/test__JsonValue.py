from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

import pytest
from projectkoios.ingestion.json.error import JsonSerializationError
from projectkoios.ingestion.json.limits.error import JsonLimitError
from projectkoios.ingestion.json.value import JsonValueProjector

from tests.projectkoios.ingestion.json.fixture import JsonFixture

FIXTURE = JsonFixture()


class FixtureKind(StrEnum):
    VALUE = "value"


@dataclass(frozen=True)
class FixtureRecord:
    text: str
    kind: FixtureKind
    path: PurePosixPath
    payload: bytes


def test__json_value_projector__projects_reviewed_immutable_values() -> None:
    projector = JsonValueProjector(FIXTURE.limits())

    projected = projector.project(
        FixtureRecord(
            text="héllo",
            kind=FixtureKind.VALUE,
            path=PurePosixPath("a/b"),
            payload=b"\x00\xff",
        )
    )

    assert projected == {
        "text": "héllo",
        "kind": "value",
        "path": "a/b",
        "payload": {"hex": "00ff"},
    }


@pytest.mark.parametrize(
    "value",
    (
        # JSON has no representation for a non-finite float.
        float("nan"),
        # Object keys are strings rather than implicitly coerced values.
        {1: "value"},
        # Unsupported mutable objects cannot silently gain a representation.
        {"value"},
    ),
)
def test__json_value_projector__rejects_unsupported_values(
    value: object,
) -> None:
    with pytest.raises(JsonSerializationError):
        JsonValueProjector(FIXTURE.limits()).project(value)


def test__json_value_projector__rejects_cycles() -> None:
    value: list[object] = []
    value.append(value)

    with pytest.raises(JsonSerializationError, match="cycle"):
        JsonValueProjector(FIXTURE.limits()).project(value)


def test__json_value_projector__applies_exact_resource_bounds() -> None:
    assert JsonValueProjector(FIXTURE.limits(maximum_items=3)).project(
        {"a": 1}
    ) == {"a": 1}
    with pytest.raises(JsonLimitError, match="item count"):
        JsonValueProjector(FIXTURE.limits(maximum_items=2)).project({"a": 1})

    assert JsonValueProjector(
        FIXTURE.limits(maximum_container_depth=2)
    ).project([[1]]) == [[1]]
    with pytest.raises(JsonLimitError, match="depth"):
        JsonValueProjector(FIXTURE.limits(maximum_container_depth=1)).project(
            [[1]]
        )

    assert (
        JsonValueProjector(FIXTURE.limits(maximum_number_characters=4)).project(
            1_234
        )
        == 1_234
    )
    with pytest.raises(JsonLimitError, match="number"):
        JsonValueProjector(FIXTURE.limits(maximum_number_characters=4)).project(
            12_345
        )

from __future__ import annotations

import pytest
from projectkoios.ingestion.json.limits.definition import (
    MAX_JSON_CONTAINER_DEPTH,
    JsonLimits,
)

from tests.projectkoios.ingestion.json.fixture import JsonFixture

FIXTURE = JsonFixture()


@pytest.mark.parametrize(
    ("field", "value", "error"),
    (
        # Boolean values must not pass as integers.
        ("maximum_items", True, TypeError),
        # Zero would make every valid document impossible.
        ("maximum_items", 0, ValueError),
        # Limit-plus-one proves the repository hard ceiling is enforced.
        ("maximum_container_depth", MAX_JSON_CONTAINER_DEPTH + 1, ValueError),
    ),
)
def test__json_limits__rejects_invalid_bounds(
    field: str,
    value: object,
    error: type[Exception],
) -> None:
    values: dict[str, object] = {
        "maximum_utf8_bytes": 4_096,
        "maximum_container_depth": 8,
        "maximum_items": 128,
        "maximum_string_bytes": 1_024,
        "maximum_total_string_bytes": 2_048,
        "maximum_number_characters": 32,
    }
    values[field] = value

    with pytest.raises(error):
        JsonLimits(**values)  # type: ignore[arg-type]


def test__json_limits__requires_consistent_string_bounds() -> None:
    with pytest.raises(ValueError, match="maximum_string_bytes"):
        FIXTURE.limits(
            maximum_string_bytes=2_049,
            maximum_total_string_bytes=2_048,
        )
    with pytest.raises(ValueError, match="maximum_total_string_bytes"):
        FIXTURE.limits(
            maximum_utf8_bytes=2_047,
            maximum_total_string_bytes=2_048,
        )

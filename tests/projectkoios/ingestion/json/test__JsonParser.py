from __future__ import annotations

import pytest
from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.json.limits.error import JsonLimitError
from projectkoios.ingestion.json.parser import JsonParser

from tests.projectkoios.ingestion.json.fixture import JsonFixture

FIXTURE = JsonFixture()


def test__json_parser__parses_strict_text_and_bytes() -> None:
    parser = JsonParser(FIXTURE.limits())
    content = '{"text":"[quoted]","values":[1,true,null]}'

    expected = {
        "text": "[quoted]",
        "values": [1, True, None],
    }
    assert parser.parse_text(content) == expected
    assert parser.parse_bytes(content.encode("utf-8")) == expected


@pytest.mark.parametrize(
    "content",
    (
        # Duplicate fields must not use last-value-wins semantics.
        '{"value":1,"value":2}',
        # Python's non-RFC constants are forbidden.
        '{"value":NaN}',
        # A finite token that overflows to infinity is also forbidden.
        '{"value":1e999}',
        # Lexically unbalanced input is rejected before recursive parsing.
        '{"value":[1}',
    ),
)
def test__json_parser__rejects_malformed_or_non_rfc_values(
    content: str,
) -> None:
    with pytest.raises(JsonParseError):
        JsonParser(FIXTURE.limits()).parse_text(content)


def test__json_parser__rejects_invalid_utf8() -> None:
    with pytest.raises(JsonParseError, match="UTF-8"):
        JsonParser(FIXTURE.limits()).parse_bytes(b'"\xff"')


def test__json_parser__applies_preparse_and_tree_limits() -> None:
    exact = b'"abc"'
    exact_limits = FIXTURE.limits(
        maximum_utf8_bytes=len(exact),
        maximum_string_bytes=3,
        maximum_total_string_bytes=3,
    )
    assert JsonParser(exact_limits).parse_bytes(exact) == "abc"
    with pytest.raises(JsonLimitError, match="content"):
        JsonParser(exact_limits).parse_bytes(exact + b" ")

    assert JsonParser(FIXTURE.limits(maximum_container_depth=2)).parse_text(
        "[[1]]"
    ) == [[1]]
    with pytest.raises(JsonLimitError, match="depth"):
        JsonParser(FIXTURE.limits(maximum_container_depth=1)).parse_text(
            "[[1]]"
        )

    assert (
        JsonParser(FIXTURE.limits(maximum_number_characters=4)).parse_text(
            "1234"
        )
        == 1_234
    )
    with pytest.raises(JsonLimitError, match="integer"):
        JsonParser(FIXTURE.limits(maximum_number_characters=4)).parse_text(
            "12345"
        )


def test__json_parser__applies_exact_tree_resource_bounds() -> None:
    limits = FIXTURE.limits(
        maximum_string_bytes=3,
        maximum_total_string_bytes=4,
    )
    assert JsonParser(limits).parse_text('["abc","d"]') == ["abc", "d"]
    with pytest.raises(JsonLimitError, match="string exceeds"):
        JsonParser(limits).parse_text('"abcd"')
    with pytest.raises(JsonLimitError, match="aggregate"):
        JsonParser(
            FIXTURE.limits(
                maximum_string_bytes=3,
                maximum_total_string_bytes=3,
            )
        ).parse_text('["ab","cd"]')

    assert JsonParser(FIXTURE.limits(maximum_items=2)).parse_text("[1]") == [1]
    with pytest.raises(JsonLimitError, match="item count"):
        JsonParser(FIXTURE.limits(maximum_items=1)).parse_text("[1]")

from __future__ import annotations

import json

import pytest
from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.pdf.batch.json import PdfBatchPlanJsonContract
from projectkoios.ingestion.pdf.batch.limits.definition import (
    MAX_PDF_BATCH_JSON_BYTES,
)
from projectkoios.ingestion.pdf.batch.limits.error import PdfBatchLimitError

from tests.projectkoios.ingestion.pdf.batch.fixture import PdfBatchFixture

FIXTURE = PdfBatchFixture()
CONTRACT = PdfBatchPlanJsonContract()


def test__pdf_batch_plan_json_contract__preserves_exact_serializer_bytes() -> (
    None
):
    plan = FIXTURE.plan()
    expected_value = {
        "schema_version": 1,
        "items": [
            {
                "source_id": item.source_id,
                "pdf_path": item.pdf_path.as_posix(),
                "output_directory": item.output_directory.as_posix(),
                "sha256": item.sha256,
                "byte_size": item.byte_size,
                "locator": item.locator,
            }
            for item in plan.items
        ],
    }
    expected = (
        json.dumps(
            expected_value,
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    assert CONTRACT.serialize_text(plan) == expected
    assert CONTRACT.serialize_bytes(plan) == expected.encode("utf-8")
    assert CONTRACT.parse_bytes(expected.encode("utf-8")) == plan


def test__pdf_batch_plan_json_contract__accepts_noncanonical_input_order() -> (
    None
):
    plan = FIXTURE.plan()
    value = json.loads(CONTRACT.serialize_text(plan))
    reordered = json.dumps(
        {"items": value["items"], "schema_version": 1},
        separators=(",", ":"),
    )

    assert CONTRACT.parse_text(reordered) == plan


@pytest.mark.parametrize(
    "content",
    (
        # Duplicate root keys must not use last-value-wins semantics.
        '{"schema_version":1,"schema_version":1,"items":[]}',
        # Non-RFC numeric constants are rejected before reconstruction.
        '{"schema_version":NaN,"items":[]}',
    ),
)
def test__pdf_batch_plan_json_contract__rejects_hardened_json_cases(
    content: str,
) -> None:
    with pytest.raises(JsonParseError):
        CONTRACT.parse_text(content)


def test__pdf_batch_plan_json_contract__rejects_malformed_utf8() -> None:
    with pytest.raises(JsonParseError, match="UTF-8"):
        CONTRACT.parse_bytes(b'{"schema_version":1,"items":["\xff"]}')


def test__pdf_batch_plan_json_contract__rejects_missing_item_fields() -> None:
    value = json.loads(CONTRACT.serialize_text(FIXTURE.plan()))
    del value["items"][0]["locator"]

    with pytest.raises(ValueError, match="missing batch item fields"):
        CONTRACT.parse_text(json.dumps(value))


def test__pdf_batch_plan_json_contract__rejects_unsafe_raw_path() -> None:
    value = json.loads(CONTRACT.serialize_text(FIXTURE.plan()))
    value["items"][0]["pdf_path"] = "../escape.pdf"

    with pytest.raises(ValueError, match="safe relative path"):
        CONTRACT.parse_text(json.dumps(value))


def test__pdf_batch_plan_json_contract__applies_exact_byte_ceiling() -> None:
    exact = b" " * MAX_PDF_BATCH_JSON_BYTES
    with pytest.raises(JsonParseError):
        CONTRACT.parse_bytes(exact)
    with pytest.raises(PdfBatchLimitError, match="content"):
        CONTRACT.parse_bytes(exact + b" ")

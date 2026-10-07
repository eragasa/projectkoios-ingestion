from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.ingestion.pdf.batch.limits.definition import (
    MAX_PDF_BATCH_ITEMS,
)
from projectkoios.ingestion.pdf.batch.limits.error import PdfBatchLimitError
from projectkoios.ingestion.pdf.batch.plan import PdfBatchPlan

from tests.projectkoios.ingestion.pdf.batch.fixture import PdfBatchFixture

FIXTURE = PdfBatchFixture()


def test__pdf_batch_plan__preserves_order_at_exact_item_limit() -> None:
    items = tuple(
        FIXTURE.item(index) for index in range(1, MAX_PDF_BATCH_ITEMS + 1)
    )

    plan = PdfBatchPlan(schema_version=1, items=items)

    assert plan.items == items


def test__pdf_batch_plan__rejects_item_limit_plus_one() -> None:
    items = tuple(
        FIXTURE.item(index) for index in range(1, MAX_PDF_BATCH_ITEMS + 2)
    )

    with pytest.raises(PdfBatchLimitError, match="item limit"):
        PdfBatchPlan(schema_version=1, items=items)


@pytest.mark.parametrize(
    "duplicate_field",
    (
        # Source identity must designate one plan item.
        "source_id",
        # One source path cannot be extracted twice in a plan.
        "pdf_path",
        # Two items cannot publish to one output directory.
        "output_directory",
    ),
)
def test__pdf_batch_plan__rejects_duplicate_identity_fields(
    duplicate_field: str,
) -> None:
    first = FIXTURE.item(1)
    second = replace(
        FIXTURE.item(2),
        **{duplicate_field: getattr(first, duplicate_field)},
    )

    with pytest.raises(ValueError, match=f"duplicate {duplicate_field}"):
        PdfBatchPlan(schema_version=1, items=(first, second))

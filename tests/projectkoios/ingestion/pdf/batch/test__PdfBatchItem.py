from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import PurePosixPath

import pytest
from projectkoios.ingestion.pdf.batch.limits.definition import (
    MAX_PDF_BATCH_TEXT_CHARACTERS,
)
from projectkoios.ingestion.pdf.batch.limits.error import PdfBatchLimitError

from tests.projectkoios.ingestion.pdf.batch.fixture import PdfBatchFixture

FIXTURE = PdfBatchFixture()


def test__pdf_batch_item__is_frozen_and_accepts_exact_text_limit() -> None:
    item = replace(
        FIXTURE.item(),
        source_id="s" * MAX_PDF_BATCH_TEXT_CHARACTERS,
        pdf_path=PurePosixPath(
            "p" * (MAX_PDF_BATCH_TEXT_CHARACTERS - 4) + ".pdf"
        ),
    )

    assert len(item.source_id) == MAX_PDF_BATCH_TEXT_CHARACTERS
    assert len(item.pdf_path.as_posix()) == MAX_PDF_BATCH_TEXT_CHARACTERS
    with pytest.raises(FrozenInstanceError):
        item.source_id = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        # Limit-plus-one proves source identity retention is bounded.
        (
            "source_id",
            "s" * (MAX_PDF_BATCH_TEXT_CHARACTERS + 1),
        ),
        # Limit-plus-one proves locator retention is independently bounded.
        (
            "locator",
            "l" * (MAX_PDF_BATCH_TEXT_CHARACTERS + 1),
        ),
        # Limit-plus-one proves portable path text is bounded directly.
        (
            "pdf_path",
            PurePosixPath("p" * (MAX_PDF_BATCH_TEXT_CHARACTERS - 3) + ".pdf"),
        ),
    ),
)
def test__pdf_batch_item__rejects_text_limit_plus_one(
    field: str,
    value: object,
) -> None:
    with pytest.raises(PdfBatchLimitError):
        replace(FIXTURE.item(), **{field: value})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        # Parent traversal is never a portable source declaration.
        ("pdf_path", PurePosixPath("../source.pdf"), "safe relative path"),
        # Output targets must remain relative to the supplied output root.
        ("output_directory", PurePosixPath("/output"), "safe relative path"),
        # A source declaration must identify PDF media by suffix.
        ("pdf_path", PurePosixPath("source.txt"), "name a PDF"),
    ),
)
def test__pdf_batch_item__rejects_invalid_paths(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        replace(FIXTURE.item(), **{field: value})


def test__pdf_batch_item__rejects_boolean_byte_size() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        replace(FIXTURE.item(), byte_size=True)

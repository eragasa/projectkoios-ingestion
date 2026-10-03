from pathlib import PurePosixPath

import pytest
from projectkoios.ingestion.batch import PdfBatchItem
from projectkoios.ingestion.ocr.batch.item import SelectiveOCRItem
from projectkoios.ingestion.ocr.batch.page import SelectiveOCRPage


def _source() -> PdfBatchItem:
    return PdfBatchItem(
        source_id="source:fixture",
        pdf_path=PurePosixPath("fixture.pdf"),
        output_directory=PurePosixPath("native/fixture"),
        sha256="a" * 64,
        byte_size=100,
    )


def test__selective_ocr_item__requires_ordered_unique_pages() -> None:
    item = SelectiveOCRItem(
        source=_source(),
        extraction_sha256="b" * 64,
        output_directory=PurePosixPath("ocr/fixture"),
        pages=(SelectiveOCRPage(1), SelectiveOCRPage(3)),
    )

    assert tuple(page.page_index for page in item.pages) == (1, 3)
    with pytest.raises(ValueError, match="unique and strictly ordered"):
        SelectiveOCRItem(
            source=_source(),
            extraction_sha256="b" * 64,
            output_directory=PurePosixPath("ocr/fixture"),
            pages=(SelectiveOCRPage(3), SelectiveOCRPage(1)),
        )


def test__selective_ocr_item__supports_one_bounded_scanned_document() -> None:
    item = SelectiveOCRItem(
        source=_source(),
        extraction_sha256="b" * 64,
        output_directory=PurePosixPath("ocr/scanned"),
        pages=tuple(SelectiveOCRPage(index) for index in range(370)),
    )

    assert len(item.pages) == 370

from pathlib import PurePosixPath

import pytest
from projectkoios.ingestion.ocr.reconciliation.batch.item import (
    SelectiveOCRReconciliationItem,
)

from tests.ocr_reconciliation_batch_support import reconciliation_fixture


def test__selective_ocr_reconciliation_item__requires_safe_ordered_pages() -> (
    None
):
    item, page, _ = reconciliation_fixture()

    assert (
        SelectiveOCRReconciliationItem.from_dict(
            {
                "source": {
                    "source_id": item.source.source_id,
                    "pdf_path": item.source.pdf_path.as_posix(),
                    "output_directory": item.source.output_directory.as_posix(),
                    "sha256": item.source.sha256,
                    "byte_size": item.source.byte_size,
                    "locator": item.source.locator,
                },
                "extraction_sha256": item.extraction_sha256,
                "ocr_directory": item.ocr_directory.as_posix(),
                "output_directory": item.output_directory.as_posix(),
                "pages": [
                    {
                        "page_index": page.page_index,
                        "ocr_publication_sha256": page.ocr_publication_sha256,
                    }
                ],
            }
        )
        == item
    )
    with pytest.raises(ValueError, match="must be safe"):
        SelectiveOCRReconciliationItem(
            source=item.source,
            extraction_sha256=item.extraction_sha256,
            ocr_directory=PurePosixPath("../ocr"),
            output_directory=item.output_directory,
            pages=item.pages,
        )

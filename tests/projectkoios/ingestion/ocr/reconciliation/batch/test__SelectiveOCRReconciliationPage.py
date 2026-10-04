import pytest
from projectkoios.ingestion.ocr.reconciliation.batch.page import (
    SelectiveOCRReconciliationPage,
)


def test__selective_ocr_reconciliation_page__is_hash_locked() -> None:
    page = SelectiveOCRReconciliationPage(
        page_index=7,
        ocr_publication_sha256="a" * 64,
    )

    assert (
        SelectiveOCRReconciliationPage.from_dict(
            {
                "page_index": 7,
                "ocr_publication_sha256": "a" * 64,
            }
        )
        == page
    )
    with pytest.raises(ValueError, match="SHA-256"):
        SelectiveOCRReconciliationPage(
            page_index=7,
            ocr_publication_sha256="changed",
        )

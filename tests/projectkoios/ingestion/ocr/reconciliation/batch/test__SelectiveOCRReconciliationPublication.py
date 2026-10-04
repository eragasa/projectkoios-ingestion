from projectkoios.ingestion.ocr.reconciliation.batch.publication import (
    SelectiveOCRReconciliationPublication,
)

from tests.ocr_reconciliation_batch_support import (
    reconciliation_fixture,
    reconciliation_result,
)


def test__selective_ocr_reconciliation_publication__binds_all_inputs() -> None:
    item, page, _ = reconciliation_fixture()
    result = reconciliation_result()

    publication = SelectiveOCRReconciliationPublication.create(
        item=item,
        page=page,
        result=result,
    )

    assert publication.source_id == item.source.source_id
    assert publication.source_sha256 == item.source.sha256
    assert publication.extraction_sha256 == item.extraction_sha256
    assert publication.ocr_publication_sha256 == page.ocr_publication_sha256
    assert publication.page_index == page.page_index
    assert publication.result is result

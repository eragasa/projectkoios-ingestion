import pytest
from projectkoios.ingestion.ocr.batch.page import SelectiveOCRPage


def test__selective_ocr_page__requires_nonnegative_integer() -> None:
    page = SelectiveOCRPage(page_index=7)

    assert page.page_index == 7
    with pytest.raises(TypeError, match="integer"):
        SelectiveOCRPage(page_index=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="nonnegative"):
        SelectiveOCRPage(page_index=-1)

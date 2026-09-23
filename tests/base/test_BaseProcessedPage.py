from __future__ import annotations

import pytest
from projectkoios.ingestion.base import BaseProcessedPage


def test__BaseProcessedPage__construct__retains_page_text() -> None:
    page = BaseProcessedPage(page_index=2, text="Source-backed text")

    assert page.page_index == 2
    assert page.text == "Source-backed text"


def test__BaseProcessedPage__construct__rejects_invalid_page_index() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        BaseProcessedPage(page_index=-1, text="Source-backed text")

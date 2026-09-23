from __future__ import annotations

import pytest
from projectkoios.ingestion.base import BaseDocument
from projectkoios.ingestion.bibtex import BibtexReferenceError


def test__BaseDocument__construction__requires_bibtex_reference() -> None:
    with pytest.raises(
        BibtexReferenceError,
        match="document requires a BibTeX reference",
    ):
        BaseDocument(
            source_id=None,  # type: ignore[arg-type]
            locator="document.pdf",
            media_type="application/pdf",
            content=b"%PDF",
        )

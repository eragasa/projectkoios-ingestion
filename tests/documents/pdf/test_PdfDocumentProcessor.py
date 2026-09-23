from __future__ import annotations

from pathlib import Path

import pytest
from projectkoios.ingestion.base import BaseProcessedPage
from projectkoios.ingestion.bibtex import BibtexParser
from projectkoios.ingestion.documents.pdf.processor import PdfDocumentProcessor
from projectkoios.ingestion.pdf import PyMuPdfExtractor
from projectkoios.ingestion.pilot import PilotDocument

pytest.importorskip("pymupdf")
_RESOURCES = Path(__file__).parents[2] / "resources" / "pilot"


def _document() -> PilotDocument:
    return PilotDocument(
        source_id=BibtexParser().parse(
            (_RESOURCES / "pilot-document.bib").read_text(encoding="utf-8"),
            "PilotDocument2026",
        ),
        locator="pilot-document.pdf",
        media_type="application/pdf",
        content=(_RESOURCES / "pilot-document.pdf").read_bytes(),
    )


def test__PdfDocumentProcessor__process__extracts_pdf_page_by_page() -> None:
    processed = PdfDocumentProcessor(
        PyMuPdfExtractor(low_text_character_threshold=0)
    ).process(_document())

    assert processed.extraction is not None
    assert processed.extraction.document.source.content_hash == (
        processed.extraction.manifest.source_content_hash
    )
    assert all(isinstance(page, BaseProcessedPage) for page in processed.pages)
    assert [page.page_index for page in processed.pages] == [0, 1]
    assert [page.text for page in processed.pages] == [
        "Alpha evidence",
        "Beta retrieval evidence",
    ]


def test__PdfDocumentProcessor__process__rejects_non_pdf_document() -> None:
    document = PilotDocument(
        source_id=_document().source_id,
        locator="pilot.txt",
        media_type="text/plain",
        content=b"not a PDF",
    )

    with pytest.raises(ValueError, match="requires application/pdf"):
        PdfDocumentProcessor().process(document)

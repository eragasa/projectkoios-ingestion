from __future__ import annotations

from projectkoios.ingestion.bibtex import BibTexRecord
from projectkoios.ingestion.documents.pdf import (
    PdfProcessedDocument,
    PdfProcessedPage,
)
from projectkoios.ingestion.pilot import (
    PilotDocument,
    PilotProcessedDocumentChunker,
)


def test__PilotProcessedDocumentChunker__chunk__preserves_page_index() -> None:
    document = PdfProcessedDocument(
        source=PilotDocument(
            source_id=BibTexRecord("pilot-source", "misc", ()),
            locator="pilot.pdf",
            media_type="application/pdf",
            content=b"%PDF",
        ),
        pages=(
            PdfProcessedPage(0, None, "Alpha evidence"),
            PdfProcessedPage(1, None, "Beta evidence"),
        ),
    )

    chunks = PilotProcessedDocumentChunker(max_characters=20).chunk(document)

    assert [chunk.page_index for chunk in chunks.chunks] == [0, 1]
    assert [chunk.text for chunk in chunks.chunks] == [
        "Alpha evidence",
        "Beta evidence",
    ]

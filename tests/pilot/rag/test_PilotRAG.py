from __future__ import annotations

from projectkoios.ingestion.base import (
    BaseProcessedDocumentChunk,
    BaseProcessedDocumentChunks,
)
from projectkoios.ingestion.bibtex import BibTexRecord
from projectkoios.ingestion.documents.pdf.models import PdfProcessedDocument
from projectkoios.ingestion.pilot import PilotDocument, PilotRAG


def test__PilotRAG__answer__returns_best_lexical_chunk() -> None:
    document = PdfProcessedDocument(
        source=PilotDocument(
            source_id=BibTexRecord("pilot-source", "misc", ()),
            locator="pilot.pdf",
            media_type="application/pdf",
            content=b"%PDF",
        ),
        pages=(),
    )
    chunks = BaseProcessedDocumentChunks(
        document=document,
        chunks=(
            BaseProcessedDocumentChunk(0, "Alpha evidence"),
            BaseProcessedDocumentChunk(1, "Beta retrieval evidence"),
        ),
    )

    answer = PilotRAG().answer("retrieval evidence", chunks)

    assert answer == "Beta retrieval evidence"

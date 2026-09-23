from __future__ import annotations

from pathlib import Path

import pytest
from projectkoios.ingestion.bibtex import BibtexParser
from projectkoios.ingestion.documents.pdf import PdfDocumentProcessor
from projectkoios.ingestion.pdf import PyMuPdfExtractor
from projectkoios.ingestion.pilot import (
    PilotDocument,
    PilotIngestionPipeline,
    PilotIngestor,
    PilotProcessedDocumentChunker,
    PilotRAG,
)

pytest.importorskip("pymupdf")
_RESOURCES = Path(__file__).parents[2] / "resources" / "pilot"


def test__PilotIngestionPipeline__ingest__stores_chunks_for_rag() -> None:
    document = PilotDocument(
        source_id=BibtexParser().parse(
            (_RESOURCES / "pilot-document.bib").read_text(encoding="utf-8"),
            "PilotDocument2026",
        ),
        locator="pilot-document.pdf",
        media_type="application/pdf",
        content=(_RESOURCES / "pilot-document.pdf").read_bytes(),
    )
    pipeline = PilotIngestionPipeline(
        ingestor=PilotIngestor(
            PdfDocumentProcessor(
                PyMuPdfExtractor(low_text_character_threshold=0)
            )
        ),
        chunker=PilotProcessedDocumentChunker(max_characters=30),
        rag=PilotRAG(),
    )

    chunks = pipeline.ingest(document)
    answer = pipeline.rag.answer("retrieval evidence", pipeline.chunks)

    assert chunks is pipeline.chunks
    assert answer == "Beta retrieval evidence"

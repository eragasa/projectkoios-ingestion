from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import (
    BaseDocument,
    BaseDocumentProcessor,
    BaseProcessedDocument,
)
from projectkoios.ingestion.bibtex import BibTexRecord
from projectkoios.ingestion.pilot import PilotDocument, PilotIngestor


@dataclass(frozen=True)
class StubProcessedDocument(BaseProcessedDocument):
    pass


class StubDocumentProcessor(BaseDocumentProcessor):
    name = "stub"
    version = "0"

    def process(self, document: BaseDocument) -> BaseProcessedDocument:
        return StubProcessedDocument(source=document)


def test__PilotIngestor__ingest__uses_configured_processor() -> None:
    document = PilotDocument(
        source_id=BibTexRecord("pilot-source", "misc", ()),
        locator="pilot.pdf",
        media_type="application/pdf",
        content=b"%PDF",
    )

    processed = PilotIngestor(StubDocumentProcessor()).ingest(document)

    assert processed.source is document

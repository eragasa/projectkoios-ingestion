from __future__ import annotations

from projectkoios.ingestion.base import (
    BaseDocument,
    BaseDocumentProcessor,
    BaseIngestor,
    BaseProcessedDocument,
)


class PilotIngestor(BaseIngestor):
    name = "pilot-ingestor"
    version = "0"

    def __init__(self, processor: BaseDocumentProcessor) -> None:
        self.processor = processor

    def ingest(self, document: BaseDocument) -> BaseProcessedDocument:
        return self.processor.process(document)

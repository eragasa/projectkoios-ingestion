from __future__ import annotations

from projectkoios.ingestion.base import (
    BaseDocument,
    BaseIngestor,
    BaseProcessedDocumentChunker,
    BaseProcessedDocumentChunks,
    BaseRAG,
)


class PilotIngestionPipeline:
    def __init__(
        self,
        ingestor: BaseIngestor,
        chunker: BaseProcessedDocumentChunker,
        rag: BaseRAG,
    ) -> None:
        self.ingestor: BaseIngestor = ingestor
        self.chunker: BaseProcessedDocumentChunker = chunker
        self.rag: BaseRAG = rag
        self.chunks: BaseProcessedDocumentChunks

    def ingest(self, document: BaseDocument) -> BaseProcessedDocumentChunks:
        processed = self.ingestor.ingest(document)
        self.chunks = self.chunker.chunk(processed)
        return self.chunks

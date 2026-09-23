from __future__ import annotations

from projectkoios.ingestion.base import (
    BaseDeterministicProcessor,
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
        deterministic_processor: BaseDeterministicProcessor,
        chunker: BaseProcessedDocumentChunker,
        rag: BaseRAG,
    ) -> None:
        self.ingestor = ingestor
        self.deterministic_processor = deterministic_processor
        self.chunker = chunker
        self.rag = rag
        self.chunks: BaseProcessedDocumentChunks

    def ingest(self, document: BaseDocument) -> BaseProcessedDocumentChunks:
        extracted = self.ingestor.ingest(document)
        processed = self.deterministic_processor.process(extracted)
        self.chunks = self.chunker.chunk(processed)
        return self.chunks

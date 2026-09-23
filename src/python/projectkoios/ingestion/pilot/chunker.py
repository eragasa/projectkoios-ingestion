from __future__ import annotations

from projectkoios.ingestion.base import (
    BaseProcessedDocument,
    BaseProcessedDocumentChunk,
    BaseProcessedDocumentChunker,
    BaseProcessedDocumentChunks,
)
from projectkoios.ingestion.documents.pdf import PdfProcessedDocument


class PilotProcessedDocumentChunker(BaseProcessedDocumentChunker):
    name = "pilot-page-character-chunker"
    version = "0"

    def __init__(self, max_characters: int = 512) -> None:
        if max_characters <= 0:
            raise ValueError("max_characters must be positive")
        self.max_characters = max_characters

    def chunk(
        self, document: BaseProcessedDocument
    ) -> BaseProcessedDocumentChunks:
        if not isinstance(document, PdfProcessedDocument):
            raise TypeError(
                "PilotProcessedDocumentChunker requires PdfProcessedDocument"
            )

        chunks = tuple(
            BaseProcessedDocumentChunk(
                page_index=page.page_index,
                text=page.text[start : start + self.max_characters],
            )
            for page in document.pages
            for start in range(0, len(page.text), self.max_characters)
        )
        return BaseProcessedDocumentChunks(
            document=document,
            chunks=chunks,
        )

from __future__ import annotations

from projectkoios.ingestion.base import (
    BaseProcessedDocumentChunks,
    BaseRAG,
)


class PilotRAG(BaseRAG):
    name = "pilot-lexical-rag"
    version = "0"

    def answer(
        self,
        question: str,
        chunks: BaseProcessedDocumentChunks,
    ) -> str:
        if not chunks.chunks:
            return ""
        words = set(question.casefold().split())
        best = max(
            chunks.chunks,
            key=lambda chunk: len(
                words.intersection(chunk.text.casefold().split())
            ),
        )
        return best.text

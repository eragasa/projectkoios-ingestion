from __future__ import annotations

from collections.abc import Iterable
from typing import BinaryIO, Protocol

from projectkoios.chunking import TextChunk
from projectkoios.ingestion.models import ExtractionResult, SourceDocument


class ChunkIndexWriter(Protocol):
    def add_chunks(self, chunks: Iterable[TextChunk]) -> None: ...


class SourceExtractor(Protocol):
    name: str
    version: str

    def extract(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractionResult: ...


class ExtractionCache(Protocol):
    def get(self, cache_key: str) -> ExtractionResult | None: ...

    def put(
        self,
        cache_key: str,
        result: ExtractionResult,
    ) -> None: ...

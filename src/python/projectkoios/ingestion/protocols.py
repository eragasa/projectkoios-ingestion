from __future__ import annotations

from collections.abc import Iterable
from typing import BinaryIO, Protocol

from projectkoios.chunking import TextChunk
from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import (
    ExtractedDocument,
    ExtractedPage,
    ExtractionResult,
    SourceDocument,
)
from projectkoios.ingestion.pdf.models import (
    PageRegionSelection,
    RenderedRegion,
)


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


class PageLayoutProcessor(Protocol):
    name: str
    version: str

    def analyze(
        self, document: ExtractedDocument
    ) -> tuple[PageLayoutResult, ...]: ...

    def analyze_page(
        self, source: SourceDocument, page: ExtractedPage
    ) -> PageLayoutResult: ...


class PageRegionRenderer(Protocol):
    name: str
    version: str

    def render(
        self,
        source: SourceDocument,
        content: BinaryIO,
        selections: Iterable[PageRegionSelection],
    ) -> tuple[RenderedRegion, ...]: ...


class ExtractionCache(Protocol):
    def get(self, cache_key: str) -> ExtractionResult | None: ...

    def put(
        self,
        cache_key: str,
        result: ExtractionResult,
    ) -> None: ...

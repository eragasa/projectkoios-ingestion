from __future__ import annotations

from collections.abc import Iterable
from typing import BinaryIO, Protocol

from projectkoios.chunking import TextChunk
from projectkoios.ingestion.equation_transcription import (
    EquationTranscriptionProcessorIdentity,
    EquationTranscriptionRequest,
    EquationTranscriptionResult,
)
from projectkoios.ingestion.equations import EquationDetectionResult
from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import (
    ExtractedDocument,
    ExtractedPage,
    ExtractionResult,
    SourceDocument,
)
from projectkoios.ingestion.ocr import (
    OCRProcessorIdentity,
    OCRRequest,
    OCRResult,
)
from projectkoios.ingestion.pdf.models import (
    PageRegionSelection,
    RenderedRegion,
)
from projectkoios.ingestion.reconciliation import (
    OCRReconciliationInput,
    OCRReconciliationResult,
)
from projectkoios.ingestion.tables import TableDetectionResult


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


class OCRProcessor(Protocol):
    """Injected OCR execution boundary; implementations remain adapters."""

    name: str
    version: str

    def identity_for(self, request: OCRRequest) -> OCRProcessorIdentity: ...

    def process(self, request: OCRRequest) -> OCRResult: ...


class OCRReconciler(Protocol):
    """Propose relationships without replacing native or OCR evidence."""

    name: str
    version: str

    def reconcile(
        self, reconciliation_input: OCRReconciliationInput
    ) -> OCRReconciliationResult: ...


class EquationCandidateDetector(Protocol):
    name: str
    version: str

    def detect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
    ) -> EquationDetectionResult: ...


class EquationTranscriptionProcessor(Protocol):
    """Injected image-to-LaTeX/MathML proposal boundary."""

    name: str
    version: str

    def identity_for(
        self, request: EquationTranscriptionRequest
    ) -> EquationTranscriptionProcessorIdentity: ...

    def process(
        self, request: EquationTranscriptionRequest
    ) -> EquationTranscriptionResult: ...


class TableCandidateDetector(Protocol):
    name: str
    version: str

    def detect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
    ) -> TableDetectionResult: ...


class ExtractionCache(Protocol):
    def get(self, cache_key: str) -> ExtractionResult | None: ...

    def put(
        self,
        cache_key: str,
        result: ExtractionResult,
    ) -> None: ...

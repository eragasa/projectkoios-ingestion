from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, BinaryIO

from projectkoios.ingestion.bibtex import (
    BibTexRecord,
    BibtexReferenceError,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.article_structure import StructureAnalysis
    from projectkoios.ingestion.equation_enrichment import (
        EquationAssemblyArtifact,
        EquationRecognitionArtifact,
    )
    from projectkoios.ingestion.equation_transcription import (
        EquationTranscriptionProcessorIdentity,
        EquationTranscriptionRequest,
        EquationTranscriptionResult,
    )
    from projectkoios.ingestion.equations import EquationDetectionResult
    from projectkoios.ingestion.figure_relevance import (
        FigureRelevanceProcessorIdentity,
        FigureRelevanceRequest,
        FigureRelevanceResult,
    )
    from projectkoios.ingestion.figures import (
        FigureDetectionConfiguration,
        FigureDetectionResult,
        FigurePageEvidence,
    )
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
    from projectkoios.ingestion.processing import (
        ProcessingInvocationResult,
        ProcessingProcessorIdentity,
        ProcessingRequest,
        ProcessingResult,
        ProcessingWorkItem,
    )
    from projectkoios.ingestion.provenance import (
        DerivationAuditInput,
        DerivationAuditReport,
    )
    from projectkoios.ingestion.reconciliation import (
        OCRReconciliationInput,
        OCRReconciliationResult,
    )
    from projectkoios.ingestion.table_structure import TableStructureResult
    from projectkoios.ingestion.tables import (
        TableDetectionConfiguration,
        TableDetectionResult,
        TablePageRuleEvidence,
    )
    from projectkoios.ingestion.transcript_projection import (
        CleanTranscriptArtifact,
    )
    from projectkoios.ingestion.transcript_v2 import CleanTranscriptV2Artifact
    from projectkoios.ingestion.transcription import (
        StructuredTranscriptionResult,
        TranscriptionInput,
    )


@dataclass(frozen=True)
class BaseDocument:
    source_id: BibTexRecord
    locator: str
    media_type: str
    content: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, BibTexRecord):
            raise BibtexReferenceError("document requires a BibTeX reference")


@dataclass(frozen=True)
class BaseProcessedDocument:
    source: BaseDocument


@dataclass(frozen=True)
class BaseProcessedPage:
    page_index: int
    text: str

    def __post_init__(self) -> None:
        if isinstance(self.page_index, bool) or not isinstance(
            self.page_index, int
        ):
            raise TypeError("page_index must be an integer")
        if self.page_index < 0:
            raise ValueError("page_index must be non-negative")
        if not isinstance(self.text, str):
            raise TypeError("page text must be a string")


@dataclass(frozen=True)
class BaseProcessedDocumentChunk:
    page_index: int
    text: str


@dataclass(frozen=True)
class BaseProcessedDocumentChunks:
    document: BaseProcessedDocument
    chunks: tuple[BaseProcessedDocumentChunk, ...]


class BaseDocumentProcessor(ABC):
    name: str
    version: str

    @abstractmethod
    def process(self, document: BaseDocument) -> BaseProcessedDocument:
        """Process one document."""


class BaseDocumentPersistanceStore(ABC):
    @abstractmethod
    def persist_bibtex(self, citation_key: str, source: str) -> str:
        """Persist exact original BibTeX text and return its location."""

    @abstractmethod
    def persist_document(self, document: BaseDocument) -> str:
        """Persist exact source-document bytes and return their location."""

    @abstractmethod
    def load_bibtex(self, location: str) -> str:
        """Load exact original BibTeX text from an explicit location."""

    @abstractmethod
    def load_document(self, location: str) -> bytes:
        """Load exact source-document bytes from an explicit location."""


class BaseDocumentPersister(ABC):
    store: BaseDocumentPersistanceStore

    @abstractmethod
    def persist(
        self,
        document: BaseDocument,
        *,
        bibtex_source: str,
    ) -> tuple[str, str]:
        """Persist one exact source document and return explicit locations."""


class BaseProcessedDocumentPersistanceStore(ABC):
    @abstractmethod
    def persist_processed_document(
        self,
        citation_key: str,
        content: bytes,
    ) -> str:
        """Persist canonical processed-document bytes and return a location."""

    @abstractmethod
    def load_processed_document(self, location: str) -> bytes:
        """Load canonical processed-document bytes from an explicit location."""


class BaseProcessedDocumentPersister(ABC):
    store: BaseProcessedDocumentPersistanceStore

    @abstractmethod
    def persist(self, document: BaseProcessedDocument) -> str:
        """Persist one canonical processed-document artifact."""


class BaseIngestor(ABC):
    name: str
    version: str

    @abstractmethod
    def ingest(self, document: BaseDocument) -> BaseProcessedDocument:
        """Ingest one document through its configured processor."""


class BaseProcessedDocumentChunker(ABC):
    name: str
    version: str

    @abstractmethod
    def chunk(
        self, document: BaseProcessedDocument
    ) -> BaseProcessedDocumentChunks:
        """Split one processed document into ordered chunks."""


class BaseRAG(ABC):
    name: str
    version: str

    @abstractmethod
    def answer(
        self,
        question: str,
        chunks: BaseProcessedDocumentChunks,
    ) -> str:
        """Answer one question from the supplied chunks."""


class BaseSourceExtractor(ABC):
    name: str
    version: str

    @abstractmethod
    def extract(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractionResult:
        """Extract one source into immutable normalized evidence."""


class BasePageLayoutProcessor(ABC):
    name: str
    version: str

    @abstractmethod
    def analyze(
        self, document: ExtractedDocument
    ) -> tuple[PageLayoutResult, ...]:
        """Analyze every page in source order."""

    @abstractmethod
    def analyze_page(
        self,
        source: SourceDocument,
        page: ExtractedPage,
    ) -> PageLayoutResult:
        """Analyze one extracted page."""


class BasePageRegionRenderer(ABC):
    name: str
    version: str

    @abstractmethod
    def render(
        self,
        source: SourceDocument,
        content: BinaryIO,
        selections: Iterable[PageRegionSelection],
    ) -> tuple[RenderedRegion, ...]:
        """Render explicit source-backed page regions."""


class BaseOcrReconciler(ABC):
    name: str
    version: str

    @abstractmethod
    def reconcile(
        self,
        reconciliation_input: OCRReconciliationInput,
    ) -> OCRReconciliationResult:
        """Relate OCR proposals to retained native evidence."""


class BaseArticleStructureAnalyzer(ABC):
    name: str
    version: str

    @abstractmethod
    def analyze(self, document: ExtractedDocument) -> StructureAnalysis:
        """Propose article structure from retained evidence."""

    @abstractmethod
    def analyze_with_layout(
        self,
        document: ExtractedDocument,
        layouts: tuple[PageLayoutResult, ...],
    ) -> StructureAnalysis:
        """Propose article structure from explicit layout evidence."""


class BaseEquationCandidateDetector(ABC):
    name: str
    version: str

    @abstractmethod
    def detect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
    ) -> EquationDetectionResult:
        """Detect source-backed equation candidates."""


class BaseEquationAssembler(ABC):
    @abstractmethod
    def assemble(
        self,
        detection: EquationDetectionResult,
        content: bytes,
    ) -> EquationAssemblyArtifact:
        """Assemble detected equation fragments without losing evidence."""


class BaseEquationRecognizer(ABC):
    @abstractmethod
    def process(
        self,
        artifact: EquationAssemblyArtifact,
    ) -> EquationRecognitionArtifact:
        """Propose recognition evidence for assembled equations."""


class BaseEquationTranscriptionProcessor(ABC):
    name: str
    version: str

    @abstractmethod
    def identity_for(
        self,
        request: EquationTranscriptionRequest,
    ) -> EquationTranscriptionProcessorIdentity:
        """Resolve the exact equation transcription processor identity."""

    @abstractmethod
    def process(
        self,
        request: EquationTranscriptionRequest,
    ) -> EquationTranscriptionResult:
        """Propose equation transcription evidence."""


class BaseTableRuleInspector(ABC):
    name: str
    version: str

    @abstractmethod
    def inspect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
        configuration: TableDetectionConfiguration,
    ) -> tuple[TablePageRuleEvidence, ...]:
        """Inspect exact PDF evidence for table rules."""


class BaseTableCandidateDetector(ABC):
    name: str
    version: str

    @abstractmethod
    def detect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
    ) -> TableDetectionResult:
        """Detect source-backed table candidates."""


class BaseTableStructureReconstructor(ABC):
    name: str
    version: str

    @abstractmethod
    def reconstruct(
        self,
        detection_result: TableDetectionResult,
    ) -> TableStructureResult:
        """Propose structure for retained table evidence."""


class BaseFigureInspector(ABC):
    name: str
    version: str

    @abstractmethod
    def inspect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
        configuration: FigureDetectionConfiguration,
    ) -> tuple[FigurePageEvidence, ...]:
        """Inspect exact PDF evidence for figure artifacts."""


class BaseFigureCandidateDetector(ABC):
    name: str
    version: str

    @abstractmethod
    def detect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
    ) -> FigureDetectionResult:
        """Detect source-backed figure candidates."""


class BaseFigureRelevanceProcessor(ABC):
    name: str
    version: str

    @abstractmethod
    def identity_for(
        self,
        request: FigureRelevanceRequest,
    ) -> FigureRelevanceProcessorIdentity:
        """Resolve the exact figure relevance processor identity."""

    @abstractmethod
    def process(
        self,
        request: FigureRelevanceRequest,
    ) -> FigureRelevanceResult:
        """Propose question-specific figure relevance evidence."""


class BaseProcessingCoordinator(ABC):
    name: str
    version: str

    @abstractmethod
    def process(self, request: ProcessingRequest) -> ProcessingResult:
        """Coordinate processing over exact bounded selections."""


class BaseProcessingProcessor(ABC):
    name: str
    version: str

    @abstractmethod
    def identity_for(
        self,
        work_item: ProcessingWorkItem,
    ) -> ProcessingProcessorIdentity:
        """Resolve the processor identity for one bounded work item."""

    @abstractmethod
    def process(
        self,
        work_item: ProcessingWorkItem,
    ) -> ProcessingInvocationResult:
        """Process one exact bounded work item."""


class BaseStructuredTranscriptionComposer(ABC):
    name: str
    version: str

    @abstractmethod
    def compose(
        self,
        transcription_input: TranscriptionInput,
    ) -> StructuredTranscriptionResult:
        """Compose retained evidence into a structured transcription."""


class BaseCleanTranscriptProjector(ABC):
    name: str
    version: str

    @abstractmethod
    def project(
        self,
        transcription_result: StructuredTranscriptionResult,
        layouts: tuple[PageLayoutResult, ...],
    ) -> CleanTranscriptArtifact:
        """Project a conservative clean transcript."""


class BaseCleanTranscriptV2Projector(ABC):
    name: str
    version: str

    @abstractmethod
    def project(
        self,
        transcription_result: StructuredTranscriptionResult,
        layouts: tuple[PageLayoutResult, ...],
    ) -> CleanTranscriptV2Artifact:
        """Project the evidence-conservative transcript-v2 contract."""


class BaseDerivationAuditValidator(ABC):
    name: str
    version: str

    @abstractmethod
    def audit(
        self,
        audit_input: DerivationAuditInput,
    ) -> DerivationAuditReport:
        """Audit retained transitive provenance."""

    @abstractmethod
    def validate(self, audit_input: DerivationAuditInput) -> None:
        """Require retained transitive provenance to be valid."""


class BaseDeterministicProcessor(ABC):
    name: str
    version: str

    @abstractmethod
    def process(
        self,
        document: BaseProcessedDocument,
    ) -> BaseProcessedDocument:
        """Execute an ordered deterministic processing prefix."""


__all__ = [
    "BaseArticleStructureAnalyzer",
    "BaseCleanTranscriptProjector",
    "BaseCleanTranscriptV2Projector",
    "BaseDerivationAuditValidator",
    "BaseDeterministicProcessor",
    "BaseDocument",
    "BaseDocumentPersistanceStore",
    "BaseDocumentPersister",
    "BaseDocumentProcessor",
    "BaseEquationAssembler",
    "BaseEquationCandidateDetector",
    "BaseEquationRecognizer",
    "BaseEquationTranscriptionProcessor",
    "BaseFigureCandidateDetector",
    "BaseFigureInspector",
    "BaseFigureRelevanceProcessor",
    "BaseIngestor",
    "BaseOcrReconciler",
    "BasePageLayoutProcessor",
    "BasePageRegionRenderer",
    "BaseProcessedDocument",
    "BaseProcessedDocumentChunk",
    "BaseProcessedDocumentChunker",
    "BaseProcessedDocumentChunks",
    "BaseProcessedDocumentPersistanceStore",
    "BaseProcessedDocumentPersister",
    "BaseProcessedPage",
    "BaseProcessingCoordinator",
    "BaseProcessingProcessor",
    "BaseRAG",
    "BaseSourceExtractor",
    "BaseStructuredTranscriptionComposer",
    "BaseTableCandidateDetector",
    "BaseTableRuleInspector",
    "BaseTableStructureReconstructor",
]

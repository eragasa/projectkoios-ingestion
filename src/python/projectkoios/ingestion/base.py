from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from projectkoios.ingestion.bibtex import (
    BibTexRecord,
    BibtexReferenceError,
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


__all__ = [
    "BaseDocument",
    "BaseDocumentProcessor",
    "BaseIngestor",
    "BaseProcessedDocument",
    "BaseProcessedDocumentChunk",
    "BaseProcessedDocumentChunker",
    "BaseProcessedDocumentChunks",
    "BaseProcessedPage",
    "BaseRAG",
]

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO

from projectkoios.ingestion.documents import ExtractedTextbook
from projectkoios.ingestion.models import ExtractedDocument, SourceDocument
from projectkoios.ingestion.structure import StructureAnalysis


class TextbookStructureAnalyzer(ABC):
    """Analyze textbook structure through a concrete implementation."""

    __slots__ = ()

    @abstractmethod
    def analyze(self, document: ExtractedDocument) -> StructureAnalysis:
        """Propose source-backed structure for one extracted textbook."""


class TextbookIngester(ABC):
    @abstractmethod
    def ingest(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractedTextbook: ...

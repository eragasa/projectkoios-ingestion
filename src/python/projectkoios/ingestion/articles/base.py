from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO

from projectkoios.ingestion.documents import ExtractedArticle
from projectkoios.ingestion.models import ExtractedDocument, SourceDocument
from projectkoios.ingestion.structure import StructureAnalysis


class ArticleStructureAnalyzer(ABC):
    """Analyze article structure through a concrete implementation."""

    __slots__ = ()

    @abstractmethod
    def analyze(self, document: ExtractedDocument) -> StructureAnalysis:
        """Propose source-backed structure for one extracted article."""


class ArticleIngester(ABC):
    @abstractmethod
    def ingest(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractedArticle: ...

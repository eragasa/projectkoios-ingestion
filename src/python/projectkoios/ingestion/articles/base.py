from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO, Protocol

from projectkoios.ingestion.documents import ExtractedArticle
from projectkoios.ingestion.models import ExtractedDocument, SourceDocument
from projectkoios.ingestion.structure import StructureAnalysis


class ArticleStructureAnalyzer(Protocol):
    def analyze(self, document: ExtractedDocument) -> StructureAnalysis: ...


class ArticleIngester(ABC):
    @abstractmethod
    def ingest(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractedArticle: ...

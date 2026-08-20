from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO, Protocol

from projectkoios.ingestion.documents import ExtractedTextbook
from projectkoios.ingestion.models import ExtractedDocument, SourceDocument
from projectkoios.ingestion.structure import StructureAnalysis


class TextbookStructureAnalyzer(Protocol):
    def analyze(self, document: ExtractedDocument) -> StructureAnalysis: ...


class TextbookIngester(ABC):
    @abstractmethod
    def ingest(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractedTextbook: ...

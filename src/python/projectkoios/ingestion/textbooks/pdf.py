from __future__ import annotations

from typing import BinaryIO

from projectkoios.ingestion.documents import ExtractedTextbook
from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.protocols import SourceExtractor
from projectkoios.ingestion.textbooks.base import (
    TextbookIngester,
    TextbookStructureAnalyzer,
)


class PdfTextbookIngester(TextbookIngester):
    def __init__(
        self,
        extractor: SourceExtractor,
        structure_analyzer: TextbookStructureAnalyzer,
    ) -> None:
        self.extractor = extractor
        self.structure_analyzer = structure_analyzer

    def ingest(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractedTextbook:
        if source.media_type != "application/pdf":
            raise ValueError("PdfTextbookIngester requires application/pdf")

        extraction = self.extractor.extract(source, content)
        if extraction.document.source != source:
            raise ValueError("extractor result does not match requested source")

        structure = self.structure_analyzer.analyze(extraction.document)
        return ExtractedTextbook(
            extraction=extraction,
            structure=structure,
            bibliographic_candidates=extraction.document.metadata,
        )

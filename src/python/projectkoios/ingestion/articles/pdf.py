from __future__ import annotations

from typing import BinaryIO

from projectkoios.ingestion.articles.base import (
    ArticleIngester,
    ArticleStructureAnalyzer,
)
from projectkoios.ingestion.documents import ExtractedArticle
from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.protocols import SourceExtractor


class PdfArticleIngester(ArticleIngester):
    def __init__(
        self,
        extractor: SourceExtractor,
        structure_analyzer: ArticleStructureAnalyzer,
    ) -> None:
        self.extractor = extractor
        self.structure_analyzer = structure_analyzer

    def ingest(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractedArticle:
        if source.media_type != "application/pdf":
            raise ValueError("PdfArticleIngester requires application/pdf")

        extraction = self.extractor.extract(source, content)
        if extraction.document.source != source:
            raise ValueError("extractor result does not match requested source")

        structure = self.structure_analyzer.analyze(extraction.document)
        return ExtractedArticle(
            extraction=extraction,
            structure=structure,
            bibliographic_candidates=extraction.document.metadata,
        )

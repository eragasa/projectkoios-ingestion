from __future__ import annotations

from typing import BinaryIO

from projectkoios.ingestion.articles.base import ArticleIngester
from projectkoios.ingestion.articles.structure.actionizer import (
    DeterministicArticleStructureActionizer,
)
from projectkoios.ingestion.articles.structure.configuration import (
    ArticleStructureConfiguration,
)
from projectkoios.ingestion.articles.structure.request import (
    ArticleStructureRequest,
)
from projectkoios.ingestion.documents import ExtractedArticle
from projectkoios.ingestion.layout import (
    DeterministicLayoutProcessor,
    PageLayoutProcessor,
)
from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.source_extractor import SourceExtractor


class PdfArticleIngester(ArticleIngester):
    def __init__(
        self,
        extractor: SourceExtractor,
        structure_actionizer: DeterministicArticleStructureActionizer,
        *,
        layout_processor: PageLayoutProcessor | None = None,
        structure_configuration: ArticleStructureConfiguration | None = None,
    ) -> None:
        if not isinstance(
            structure_actionizer, DeterministicArticleStructureActionizer
        ):
            raise TypeError(
                "structure_actionizer must be "
                "DeterministicArticleStructureActionizer"
            )
        self.extractor = extractor
        self.layout_processor = (
            DeterministicLayoutProcessor()
            if layout_processor is None
            else layout_processor
        )
        self.structure_actionizer = structure_actionizer
        self.structure_configuration = (
            ArticleStructureConfiguration()
            if structure_configuration is None
            else structure_configuration
        )

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

        layouts = self.layout_processor.analyze(extraction.document)
        structure = self.structure_actionizer.action(
            request=ArticleStructureRequest.create(
                document=extraction.document,
                layouts=layouts,
                configuration=self.structure_configuration,
            )
        )
        return ExtractedArticle(
            extraction=extraction,
            structure=structure,
            bibliographic_candidates=extraction.document.metadata,
        )

"""Article-structure analyzer deterministic."""

from __future__ import annotations

from projectkoios.ingestion.articles.structure.analyzer.base import (
    ArticleStructureAnalyzer,
)
from projectkoios.ingestion.articles.structure.configuration import (
    ArticleStructureConfiguration,
)
from projectkoios.ingestion.articles.structure.constants import (
    ARTICLE_STRUCTURE_PROCESSOR_VERSION,
)
from projectkoios.ingestion.articles.structure.evidence.text import (
    _ordered_text_evidence,
)
from projectkoios.ingestion.articles.structure.limits.error import (
    ArticleStructureLimitError,
)
from projectkoios.ingestion.articles.structure.proposal.derivation import (
    _propose,
)
from projectkoios.ingestion.articles.structure.result.derivation import (
    _materialize,
)
from projectkoios.ingestion.articles.structure.validation.input import (
    _validate_input,
)
from projectkoios.ingestion.layout import (
    DeterministicLayoutProcessor,
    PageLayoutProcessor,
    PageLayoutResult,
)
from projectkoios.ingestion.models import (
    ExtractedDocument,
)
from projectkoios.ingestion.structure import (
    StructureAnalysis,
)


class DeterministicArticleStructureAnalyzer(ArticleStructureAnalyzer):
    """Propose bounded article structure from exact text/layout evidence."""

    name = "deterministic-article-structure"
    version = ARTICLE_STRUCTURE_PROCESSOR_VERSION

    def __init__(
        self,
        configuration: ArticleStructureConfiguration | None = None,
        *,
        layout_processor: PageLayoutProcessor | None = None,
    ) -> None:
        self.configuration = configuration or ArticleStructureConfiguration()
        self.layout_processor = (
            layout_processor or DeterministicLayoutProcessor()
        )

    @property
    def configuration_digest(self) -> str:
        return self.configuration.configuration_digest

    def analyze(self, document: ExtractedDocument) -> StructureAnalysis:
        layouts = self.layout_processor.analyze(document)
        return self.analyze_with_layout(document, layouts)

    def analyze_with_layout(
        self,
        document: ExtractedDocument,
        layouts: tuple[PageLayoutResult, ...],
    ) -> StructureAnalysis:
        _validate_input(document, layouts, self.configuration)
        text_evidence = _ordered_text_evidence(
            document, layouts, self.configuration
        )
        proposals, warning_proposals = _propose(
            document,
            layouts,
            text_evidence,
            self.configuration,
        )
        if len(proposals) > self.configuration.max_nodes:
            raise ArticleStructureLimitError("proposed nodes exceed max_nodes")
        if len(warning_proposals) > self.configuration.max_warnings:
            raise ArticleStructureLimitError(
                "structure warnings exceed max_warnings"
            )
        nodes, warnings = _materialize(proposals, warning_proposals)
        return StructureAnalysis.create(
            source=document.source,
            nodes=nodes,
            warnings=warnings,
            layout_result_ids=tuple(layout.result_id for layout in layouts),
            input_block_ids=tuple(
                block.block_id
                for page in document.pages
                for block in page.blocks
            ),
            processor_name=self.name,
            processor_version=self.version,
            configuration_digest=self.configuration_digest,
        )

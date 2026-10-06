"""Deterministic article-structure actionizer."""

from __future__ import annotations

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
from projectkoios.ingestion.articles.structure.request import (
    ArticleStructureRequest,
)
from projectkoios.ingestion.articles.structure.result.derivation import (
    _materialize,
)
from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.structure import StructureAnalysis


class DeterministicArticleStructureActionizer(
    ConfigurableDataObjectActionizer[
        ArticleStructureConfiguration,
        ArticleStructureRequest,
        StructureAnalysis,
    ]
):
    """Propose bounded article structure from exact request evidence."""

    __slots__ = ()

    actionizer_name = "deterministic-article-structure"
    actionizer_version = ARTICLE_STRUCTURE_PROCESSOR_VERSION
    configuration_type = ArticleStructureConfiguration

    def action(self, *, request: ArticleStructureRequest) -> StructureAnalysis:
        if type(request) is not ArticleStructureRequest:
            raise TypeError("request must be an ArticleStructureRequest")
        configuration = self._require_configuration(request=request)
        text_evidence = _ordered_text_evidence(
            request.document,
            request.layouts,
            configuration,
        )
        proposals, warning_proposals = _propose(
            request.document,
            request.layouts,
            text_evidence,
            configuration,
        )
        if len(proposals) > configuration.max_nodes:
            raise ArticleStructureLimitError("proposed nodes exceed max_nodes")
        if len(warning_proposals) > configuration.max_warnings:
            raise ArticleStructureLimitError(
                "structure warnings exceed max_warnings"
            )
        nodes, warnings = _materialize(proposals, warning_proposals)
        return StructureAnalysis.create(
            source=request.document.source,
            nodes=nodes,
            warnings=warnings,
            layout_result_ids=tuple(
                layout.result_id for layout in request.layouts
            ),
            input_block_ids=tuple(
                block.block_id
                for page in request.document.pages
                for block in page.blocks
            ),
            processor_name=self.actionizer_name,
            processor_version=self.actionizer_version,
            configuration_digest=configuration.configuration_digest,
        )

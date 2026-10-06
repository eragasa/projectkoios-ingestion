"""Aggregate figure-relevance action result."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.figures.relevance.cache.identity import (
    build_figure_relevance_cache_key,
)
from projectkoios.ingestion.figures.relevance.constants import (
    FIGURE_RELEVANCE_CONTRACT_VERSION,
)
from projectkoios.ingestion.figures.relevance.identity import (
    result as result_identity,
)
from projectkoios.ingestion.figures.relevance.identity.processor import (
    FigureRelevanceProcessorIdentity,
)
from projectkoios.ingestion.figures.relevance.request import (
    FigureRelevanceRequest,
)
from projectkoios.ingestion.figures.relevance.result.selection import (
    FigureRelevanceSelectionResult,
)
from projectkoios.ingestion.figures.relevance.validation import (
    result as result_validation,
)


@dataclass(frozen=True)
class FigureRelevanceResult(DataObjectActionResult):
    result_id: str
    request: FigureRelevanceRequest
    processor_identity: FigureRelevanceProcessorIdentity
    selection_results: tuple[FigureRelevanceSelectionResult, ...]
    cache_key: str
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: FigureRelevanceRequest,
        processor_identity: FigureRelevanceProcessorIdentity,
        selection_results: tuple[FigureRelevanceSelectionResult, ...],
    ) -> FigureRelevanceResult:
        cache_key = build_figure_relevance_cache_key(
            request, processor_identity
        )
        result_id = result_identity._result_id(
            request.request_id,
            processor_identity,
            selection_results,
            cache_key,
        )
        return cls(
            result_id=result_id,
            request=request,
            processor_identity=processor_identity,
            selection_results=selection_results,
            cache_key=cache_key,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError("unsupported figure-relevance result version")
        result_validation._validate_result(self)
        expected = result_identity._result_id(
            self.request.request_id,
            self.processor_identity,
            self.selection_results,
            self.cache_key,
        )
        if self.result_id != expected:
            raise ValueError("figure-relevance result ID is inconsistent")

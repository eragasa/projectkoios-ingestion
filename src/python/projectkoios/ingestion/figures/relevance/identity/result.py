"""Stable result-id derivation."""

from __future__ import annotations

from projectkoios.ingestion.figures.relevance.identity.processor import (
    FigureRelevanceProcessorIdentity,
)
from projectkoios.ingestion.figures.relevance.result.selection import (
    FigureRelevanceSelectionResult,
)
from projectkoios.ingestion.identity import stable_id


def _result_id(
    request_id: str,
    processor_identity: FigureRelevanceProcessorIdentity,
    selection_results: tuple[FigureRelevanceSelectionResult, ...],
    cache_key: str,
) -> str:
    return stable_id(
        "figure-relevance-result",
        request_id,
        processor_identity.identity_parts(),
        tuple(item.selection_result_id for item in selection_results),
        cache_key,
    )

"""Figure-relevance cache identity derivation."""

from __future__ import annotations

from projectkoios.ingestion.figures.relevance.constants import (
    FIGURE_RELEVANCE_CONFIGURATION_VERSION,
    FIGURE_RELEVANCE_CONTRACT_VERSION,
)
from projectkoios.ingestion.figures.relevance.identity.processor import (
    FigureRelevanceProcessorIdentity,
)
from projectkoios.ingestion.figures.relevance.limits.error import (
    FigureRelevanceLimitError,
)
from projectkoios.ingestion.figures.relevance.request import (
    FigureRelevanceRequest,
)
from projectkoios.ingestion.identity import stable_id


def build_figure_relevance_cache_key(
    request: FigureRelevanceRequest,
    processor_identity: FigureRelevanceProcessorIdentity,
) -> str:
    if not isinstance(request, FigureRelevanceRequest):
        raise TypeError("request must be FigureRelevanceRequest")
    if not isinstance(processor_identity, FigureRelevanceProcessorIdentity):
        raise TypeError(
            "processor_identity must be FigureRelevanceProcessorIdentity"
        )
    if len(processor_identity.resources) > request.configuration.max_resources:
        raise FigureRelevanceLimitError("resources exceed max_resources")
    return stable_id(
        "figure-relevance-cache",
        FIGURE_RELEVANCE_CONTRACT_VERSION,
        FIGURE_RELEVANCE_CONFIGURATION_VERSION,
        request.request_id,
        processor_identity.identity_parts(),
    )

"""Stable request-id derivation."""

from __future__ import annotations

from projectkoios.ingestion.figures.relevance.configuration import (
    FigureRelevanceConfiguration,
)
from projectkoios.ingestion.figures.relevance.constants import (
    FIGURE_RELEVANCE_CONFIGURATION_VERSION,
    FIGURE_RELEVANCE_CONTRACT_VERSION,
)
from projectkoios.ingestion.figures.relevance.selection import (
    FigureRelevanceSelection,
)
from projectkoios.ingestion.identity import stable_id


def _request_id(
    review_question: str,
    selections: tuple[FigureRelevanceSelection, ...],
    configuration: FigureRelevanceConfiguration,
) -> str:
    return stable_id(
        "figure-relevance-request",
        FIGURE_RELEVANCE_CONTRACT_VERSION,
        FIGURE_RELEVANCE_CONFIGURATION_VERSION,
        review_question,
        tuple(
            (
                selection.selection_id,
                selection.detection_result.result_id,
                selection.candidate_id,
            )
            for selection in selections
        ),
        configuration.identity_parts(),
    )

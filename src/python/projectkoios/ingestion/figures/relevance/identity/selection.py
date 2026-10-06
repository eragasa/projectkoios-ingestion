"""Stable selection-result-id derivation."""

from __future__ import annotations

from projectkoios.ingestion.figures.relevance.failure import (
    FigureRelevanceFailure,
)
from projectkoios.ingestion.figures.relevance.proposal import (
    FigureRelevanceProposal,
)
from projectkoios.ingestion.figures.relevance.status.result import (
    FigureRelevanceStatus,
)
from projectkoios.ingestion.figures.relevance.warning import (
    FigureRelevanceWarning,
)
from projectkoios.ingestion.identity import stable_id


def _selection_result_id(
    selection_id: str,
    candidate_id: str,
    status: FigureRelevanceStatus,
    proposal: FigureRelevanceProposal | None,
    warnings: tuple[FigureRelevanceWarning, ...],
    failures: tuple[FigureRelevanceFailure, ...],
) -> str:
    return stable_id(
        "figure-relevance-selection-result",
        selection_id,
        candidate_id,
        status.value,
        proposal.proposal_id if proposal is not None else None,
        tuple(item.warning_id for item in warnings),
        tuple(item.failure_id for item in failures),
    )

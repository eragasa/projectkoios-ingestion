"""Stable proposal-id derivation."""

from __future__ import annotations

from projectkoios.ingestion.figures.relevance.confidence import (
    FigureRelevanceConfidence,
)
from projectkoios.ingestion.figures.relevance.level import FigureRelevanceLevel
from projectkoios.ingestion.figures.relevance.score import FigureRelevanceScore
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import Metadata


def _proposal_id(
    selection_id: str,
    candidate_id: str,
    configuration_digest: str,
    level: FigureRelevanceLevel,
    score: FigureRelevanceScore,
    confidence: FigureRelevanceConfidence | None,
    rationale: str,
    evidence_component_ids: tuple[str, ...],
    evidence_association_ids: tuple[str, ...],
    evidence: Metadata,
) -> str:
    return stable_id(
        "figure-relevance-proposal",
        selection_id,
        candidate_id,
        configuration_digest,
        level.value,
        score.identity_parts(),
        confidence.identity_parts() if confidence is not None else None,
        rationale,
        evidence_component_ids,
        evidence_association_ids,
        evidence,
    )

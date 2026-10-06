"""Figure-relevance proposal validation."""

from __future__ import annotations

from projectkoios.ingestion.figures.relevance.configuration import (
    FigureRelevanceConfiguration,
)
from projectkoios.ingestion.figures.relevance.limits.error import (
    FigureRelevanceLimitError,
)
from projectkoios.ingestion.figures.relevance.validation import (
    proposal as proposal_validation,
)
from projectkoios.ingestion.figures.relevance.validation import (
    value as value_validation,
)
from projectkoios.ingestion.models import Metadata


def _validate_configured_proposal_evidence(
    component_ids: tuple[str, ...],
    association_ids: tuple[str, ...],
    evidence: Metadata,
    configuration: FigureRelevanceConfiguration,
) -> None:
    proposal_validation._validate_configured_metadata(evidence, configuration)
    proposal_validation._validate_proposal_evidence_limits(
        component_ids,
        association_ids,
        evidence,
        configuration.max_evidence_entries,
        configuration.max_evidence_characters,
    )


def _validate_proposal_evidence_limits(
    component_ids: tuple[str, ...],
    association_ids: tuple[str, ...],
    evidence: Metadata,
    max_entries: int,
    max_characters: int,
) -> None:
    if len(component_ids) + len(association_ids) + len(evidence) > max_entries:
        raise FigureRelevanceLimitError(
            "proposal evidence exceeds max_evidence_entries"
        )
    if (
        sum(len(value) for value in component_ids)
        + sum(len(value) for value in association_ids)
        + sum(len(key) + len(value) for key, value in evidence)
        > max_characters
    ):
        raise FigureRelevanceLimitError(
            "proposal evidence exceeds max_evidence_characters"
        )


def _validate_configured_metadata(
    value: Metadata,
    configuration: FigureRelevanceConfiguration,
) -> None:
    value_validation._validate_metadata(value)
    if len(value) > configuration.max_evidence_entries:
        raise FigureRelevanceLimitError("evidence exceeds max_evidence_entries")
    if sum(len(key) + len(item) for key, item in value) > (
        configuration.max_evidence_characters
    ):
        raise FigureRelevanceLimitError(
            "evidence exceeds max_evidence_characters"
        )

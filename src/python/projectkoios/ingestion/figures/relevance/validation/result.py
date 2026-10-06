"""Figure-relevance result validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectkoios.ingestion.figures.relevance.cache.identity import (
    build_figure_relevance_cache_key,
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
from projectkoios.ingestion.figures.relevance.result.selection import (
    FigureRelevanceSelectionResult,
)
from projectkoios.ingestion.figures.relevance.validation import (
    proposal as proposal_validation,
)
from projectkoios.ingestion.figures.relevance.validation import (
    value as value_validation,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.figures.relevance.result.aggregate import (
        FigureRelevanceResult,
    )


def _validate_result(result: FigureRelevanceResult) -> None:
    if not isinstance(result.request, FigureRelevanceRequest):
        raise TypeError("result request is unsupported")
    if not isinstance(
        result.processor_identity, FigureRelevanceProcessorIdentity
    ):
        raise TypeError("result processor identity is unsupported")
    configuration = result.request.configuration
    if len(result.processor_identity.resources) > configuration.max_resources:
        raise FigureRelevanceLimitError("resources exceed max_resources")
    expected_cache_key = build_figure_relevance_cache_key(
        result.request, result.processor_identity
    )
    if result.cache_key != expected_cache_key:
        raise ValueError("figure-relevance cache key is inconsistent")
    value_validation._require_tuple(
        "selection results", result.selection_results
    )
    if any(
        not isinstance(item, FigureRelevanceSelectionResult)
        for item in result.selection_results
    ):
        raise TypeError("selection results contain an unsupported value")
    if tuple(item.selection_id for item in result.selection_results) != tuple(
        item.selection_id for item in result.request.selections
    ):
        raise ValueError("selection result order or coverage is inconsistent")
    if tuple(item.candidate_id for item in result.selection_results) != tuple(
        item.candidate_id for item in result.request.selections
    ):
        raise ValueError("selection candidate coverage is inconsistent")
    total_warnings = 0
    total_failures = 0
    total_rationale = 0
    selection_by_id = {
        item.selection_id: item for item in result.request.selections
    }
    for item in result.selection_results:
        selection = selection_by_id[item.selection_id]
        if len(item.warnings) > configuration.max_warnings_per_selection:
            raise FigureRelevanceLimitError(
                "selection warnings exceed max_warnings_per_selection"
            )
        if len(item.failures) > configuration.max_failures_per_selection:
            raise FigureRelevanceLimitError(
                "selection failures exceed max_failures_per_selection"
            )
        total_warnings += len(item.warnings)
        total_failures += len(item.failures)
        for warning in item.warnings:
            if (
                len(warning.message)
                > configuration.max_warning_message_characters
            ):
                raise FigureRelevanceLimitError(
                    "warning message exceeds configured limit"
                )
            if (
                warning.suggested_recovery is not None
                and len(warning.suggested_recovery)
                > configuration.max_warning_message_characters
            ):
                raise FigureRelevanceLimitError(
                    "suggested recovery exceeds configured limit"
                )
            proposal_validation._validate_configured_metadata(
                warning.evidence, configuration
            )
        for failure in item.failures:
            if (
                len(failure.message)
                > configuration.max_failure_message_characters
            ):
                raise FigureRelevanceLimitError(
                    "failure message exceeds configured limit"
                )
            proposal_validation._validate_configured_metadata(
                failure.evidence, configuration
            )
        proposal = item.proposal
        if proposal is None:
            continue
        if proposal.configuration_digest != configuration.configuration_digest:
            raise ValueError("proposal configuration is inconsistent")
        if proposal.level is not configuration.level_for(proposal.score):
            raise ValueError("proposal level is inconsistent with its score")
        if len(proposal.rationale) > configuration.max_rationale_characters:
            raise FigureRelevanceLimitError(
                "proposal rationale exceeds configured limit"
            )
        total_rationale += len(proposal.rationale)
        candidate = selection.candidate
        component_ids = {
            component.component_id for component in candidate.components
        }
        association_ids = {
            association.association_id for association in candidate.associations
        }
        if not set(proposal.evidence_component_ids).issubset(component_ids):
            raise ValueError("proposal references an unknown figure component")
        if not set(proposal.evidence_association_ids).issubset(association_ids):
            raise ValueError(
                "proposal references an unknown figure association"
            )
        proposal_validation._validate_configured_proposal_evidence(
            proposal.evidence_component_ids,
            proposal.evidence_association_ids,
            proposal.evidence,
            configuration,
        )
    if total_warnings > configuration.max_total_warnings:
        raise FigureRelevanceLimitError("warnings exceed max_total_warnings")
    if total_failures > configuration.max_total_failures:
        raise FigureRelevanceLimitError("failures exceed max_total_failures")
    if total_rationale > configuration.max_total_rationale_characters:
        raise FigureRelevanceLimitError(
            "rationales exceed max_total_rationale_characters"
        )
    value_validation._validate_retained_size(
        result, configuration.max_result_bytes
    )

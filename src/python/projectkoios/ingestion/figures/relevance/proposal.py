"""Figure-relevance proposal record."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.figures.relevance.confidence import (
    FigureRelevanceConfidence,
)
from projectkoios.ingestion.figures.relevance.configuration import (
    FigureRelevanceConfiguration,
)
from projectkoios.ingestion.figures.relevance.constants import (
    FIGURE_RELEVANCE_CONTRACT_VERSION,
)
from projectkoios.ingestion.figures.relevance.identity import (
    proposal as proposal_identity,
)
from projectkoios.ingestion.figures.relevance.level import FigureRelevanceLevel
from projectkoios.ingestion.figures.relevance.limits.definition import (
    _MAX_EVIDENCE_CHARACTERS,
    _MAX_EVIDENCE_ENTRIES,
    _MAX_RATIONALE_CHARACTERS,
)
from projectkoios.ingestion.figures.relevance.score import FigureRelevanceScore
from projectkoios.ingestion.figures.relevance.selection import (
    FigureRelevanceSelection,
)
from projectkoios.ingestion.figures.relevance.validation import (
    proposal as proposal_validation,
)
from projectkoios.ingestion.figures.relevance.validation import (
    value as value_validation,
)
from projectkoios.ingestion.models import Metadata


@dataclass(frozen=True)
class FigureRelevanceProposal:
    proposal_id: str
    selection_id: str
    candidate_id: str
    configuration_digest: str
    level: FigureRelevanceLevel
    score: FigureRelevanceScore
    confidence: FigureRelevanceConfidence | None
    rationale: str
    evidence_component_ids: tuple[str, ...]
    evidence_association_ids: tuple[str, ...]
    evidence: Metadata
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection: FigureRelevanceSelection,
        configuration: FigureRelevanceConfiguration,
        score: FigureRelevanceScore,
        confidence: FigureRelevanceConfidence | None,
        rationale: str,
        evidence_component_ids: tuple[str, ...] = (),
        evidence_association_ids: tuple[str, ...] = (),
        evidence: Metadata = (),
    ) -> FigureRelevanceProposal:
        if not isinstance(selection, FigureRelevanceSelection):
            raise TypeError("selection must be FigureRelevanceSelection")
        if not isinstance(configuration, FigureRelevanceConfiguration):
            raise TypeError(
                "configuration must be FigureRelevanceConfiguration"
            )
        if not isinstance(score, FigureRelevanceScore):
            raise TypeError("score must be FigureRelevanceScore")
        if confidence is not None and not isinstance(
            confidence, FigureRelevanceConfidence
        ):
            raise TypeError("confidence must be FigureRelevanceConfidence")
        value_validation._bounded_string(
            "figure-relevance rationale",
            rationale,
            nonempty=True,
            limit=configuration.max_rationale_characters,
        )
        value_validation._unique_strings(
            "evidence component IDs", evidence_component_ids
        )
        value_validation._unique_strings(
            "evidence association IDs", evidence_association_ids
        )
        proposal_validation._validate_configured_proposal_evidence(
            evidence_component_ids,
            evidence_association_ids,
            evidence,
            configuration,
        )
        candidate = selection.candidate
        if not set(evidence_component_ids).issubset(
            component.component_id for component in candidate.components
        ):
            raise ValueError("proposal references an unknown figure component")
        if not set(evidence_association_ids).issubset(
            association.association_id for association in candidate.associations
        ):
            raise ValueError(
                "proposal references an unknown figure association"
            )
        level = configuration.level_for(score)
        digest = configuration.configuration_digest
        proposal_id = proposal_identity._proposal_id(
            selection.selection_id,
            selection.candidate_id,
            digest,
            level,
            score,
            confidence,
            rationale,
            evidence_component_ids,
            evidence_association_ids,
            evidence,
        )
        return cls(
            proposal_id=proposal_id,
            selection_id=selection.selection_id,
            candidate_id=selection.candidate_id,
            configuration_digest=digest,
            level=level,
            score=score,
            confidence=confidence,
            rationale=rationale,
            evidence_component_ids=evidence_component_ids,
            evidence_association_ids=evidence_association_ids,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError("unsupported figure-relevance proposal version")
        value_validation._identity_fields(
            self.selection_id, self.candidate_id, self.configuration_digest
        )
        if not isinstance(self.level, FigureRelevanceLevel):
            raise TypeError("figure-relevance level is unsupported")
        if not isinstance(self.score, FigureRelevanceScore):
            raise TypeError("figure-relevance score is unsupported")
        if self.confidence is not None and not isinstance(
            self.confidence, FigureRelevanceConfidence
        ):
            raise TypeError("figure-relevance confidence is unsupported")
        value_validation._bounded_string(
            "figure-relevance rationale",
            self.rationale,
            nonempty=True,
            limit=_MAX_RATIONALE_CHARACTERS,
        )
        if not self.rationale.strip():
            raise ValueError("figure-relevance rationale must contain text")
        value_validation._unique_strings(
            "evidence component IDs", self.evidence_component_ids
        )
        value_validation._unique_strings(
            "evidence association IDs", self.evidence_association_ids
        )
        value_validation._validate_metadata(self.evidence)
        proposal_validation._validate_proposal_evidence_limits(
            self.evidence_component_ids,
            self.evidence_association_ids,
            self.evidence,
            _MAX_EVIDENCE_ENTRIES,
            _MAX_EVIDENCE_CHARACTERS,
        )
        expected = proposal_identity._proposal_id(
            self.selection_id,
            self.candidate_id,
            self.configuration_digest,
            self.level,
            self.score,
            self.confidence,
            self.rationale,
            self.evidence_component_ids,
            self.evidence_association_ids,
            self.evidence,
        )
        if self.proposal_id != expected:
            raise ValueError("figure-relevance proposal ID is inconsistent")

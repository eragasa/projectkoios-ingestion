"""Figure-relevance failure record."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.figures.relevance.constants import (
    FIGURE_RELEVANCE_CONTRACT_VERSION,
)
from projectkoios.ingestion.figures.relevance.kind.failure import (
    FigureRelevanceFailureKind,
)
from projectkoios.ingestion.figures.relevance.limits.definition import (
    _MAX_FAILURE_MESSAGE_CHARACTERS,
)
from projectkoios.ingestion.figures.relevance.validation import (
    value as value_validation,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import Metadata


@dataclass(frozen=True)
class FigureRelevanceFailure:
    failure_id: str
    selection_id: str
    kind: FigureRelevanceFailureKind
    message: str
    retryable: bool
    evidence: Metadata = ()
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection_id: str,
        kind: FigureRelevanceFailureKind,
        message: str,
        retryable: bool,
        evidence: Metadata = (),
    ) -> FigureRelevanceFailure:
        failure_id = stable_id(
            "figure-relevance-failure",
            selection_id,
            kind.value,
            message,
            retryable,
            evidence,
        )
        return cls(
            failure_id=failure_id,
            selection_id=selection_id,
            kind=kind,
            message=message,
            retryable=retryable,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError("unsupported figure-relevance failure version")
        value_validation._identity_fields(self.selection_id)
        if not isinstance(self.kind, FigureRelevanceFailureKind):
            raise TypeError("figure-relevance failure kind is unsupported")
        value_validation._bounded_string(
            "failure message",
            self.message,
            nonempty=True,
            limit=_MAX_FAILURE_MESSAGE_CHARACTERS,
        )
        if not isinstance(self.retryable, bool):
            raise TypeError("failure retryable must be a boolean")
        value_validation._validate_metadata(self.evidence)
        expected = stable_id(
            "figure-relevance-failure",
            self.selection_id,
            self.kind.value,
            self.message,
            self.retryable,
            self.evidence,
        )
        if self.failure_id != expected:
            raise ValueError("figure-relevance failure ID is inconsistent")

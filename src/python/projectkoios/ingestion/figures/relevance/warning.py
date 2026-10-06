"""Figure-relevance warning record."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.figures.relevance.constants import (
    FIGURE_RELEVANCE_CONTRACT_VERSION,
)
from projectkoios.ingestion.figures.relevance.limits.definition import (
    _MAX_WARNING_MESSAGE_CHARACTERS,
)
from projectkoios.ingestion.figures.relevance.validation import (
    value as value_validation,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import Metadata, WarningSeverity


@dataclass(frozen=True)
class FigureRelevanceWarning:
    warning_id: str
    selection_id: str
    code: str
    severity: WarningSeverity
    message: str
    evidence: Metadata = ()
    suggested_recovery: str | None = None
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection_id: str,
        code: str,
        severity: WarningSeverity,
        message: str,
        evidence: Metadata = (),
        suggested_recovery: str | None = None,
    ) -> FigureRelevanceWarning:
        warning_id = stable_id(
            "figure-relevance-warning",
            selection_id,
            code,
            severity.value,
            message,
            evidence,
            suggested_recovery,
        )
        return cls(
            warning_id=warning_id,
            selection_id=selection_id,
            code=code,
            severity=severity,
            message=message,
            evidence=evidence,
            suggested_recovery=suggested_recovery,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError("unsupported figure-relevance warning version")
        value_validation._identity_fields(self.selection_id, self.code)
        if not isinstance(self.severity, WarningSeverity):
            raise TypeError("figure-relevance warning severity is unsupported")
        value_validation._bounded_string(
            "warning message",
            self.message,
            nonempty=True,
            limit=_MAX_WARNING_MESSAGE_CHARACTERS,
        )
        value_validation._validate_metadata(self.evidence)
        if self.suggested_recovery is not None:
            value_validation._bounded_string(
                "suggested recovery",
                self.suggested_recovery,
                nonempty=True,
                limit=_MAX_WARNING_MESSAGE_CHARACTERS,
            )
        expected = stable_id(
            "figure-relevance-warning",
            self.selection_id,
            self.code,
            self.severity.value,
            self.message,
            self.evidence,
            self.suggested_recovery,
        )
        if self.warning_id != expected:
            raise ValueError("figure-relevance warning ID is inconsistent")

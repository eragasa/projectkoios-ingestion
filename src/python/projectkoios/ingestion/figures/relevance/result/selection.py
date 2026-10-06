"""Per-selection figure-relevance result."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.figures.relevance.constants import (
    FIGURE_RELEVANCE_CONTRACT_VERSION,
)
from projectkoios.ingestion.figures.relevance.failure import (
    FigureRelevanceFailure,
)
from projectkoios.ingestion.figures.relevance.identity import (
    selection as selection_identity,
)
from projectkoios.ingestion.figures.relevance.limits.definition import (
    _MAX_FAILURES_PER_SELECTION,
    _MAX_WARNINGS_PER_SELECTION,
)
from projectkoios.ingestion.figures.relevance.limits.error import (
    FigureRelevanceLimitError,
)
from projectkoios.ingestion.figures.relevance.proposal import (
    FigureRelevanceProposal,
)
from projectkoios.ingestion.figures.relevance.selection import (
    FigureRelevanceSelection,
)
from projectkoios.ingestion.figures.relevance.status.result import (
    FigureRelevanceStatus,
)
from projectkoios.ingestion.figures.relevance.validation import (
    value as value_validation,
)
from projectkoios.ingestion.figures.relevance.warning import (
    FigureRelevanceWarning,
)


@dataclass(frozen=True)
class FigureRelevanceSelectionResult:
    selection_result_id: str
    selection_id: str
    candidate_id: str
    status: FigureRelevanceStatus
    proposal: FigureRelevanceProposal | None
    warnings: tuple[FigureRelevanceWarning, ...]
    failures: tuple[FigureRelevanceFailure, ...]
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection: FigureRelevanceSelection,
        status: FigureRelevanceStatus,
        proposal: FigureRelevanceProposal | None,
        warnings: tuple[FigureRelevanceWarning, ...] = (),
        failures: tuple[FigureRelevanceFailure, ...] = (),
    ) -> FigureRelevanceSelectionResult:
        selection_result_id = selection_identity._selection_result_id(
            selection.selection_id,
            selection.candidate_id,
            status,
            proposal,
            warnings,
            failures,
        )
        return cls(
            selection_result_id=selection_result_id,
            selection_id=selection.selection_id,
            candidate_id=selection.candidate_id,
            status=status,
            proposal=proposal,
            warnings=warnings,
            failures=failures,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError(
                "unsupported figure-relevance selection-result version"
            )
        value_validation._identity_fields(self.selection_id, self.candidate_id)
        if not isinstance(self.status, FigureRelevanceStatus):
            raise TypeError("figure-relevance status is unsupported")
        if self.proposal is not None and not isinstance(
            self.proposal, FigureRelevanceProposal
        ):
            raise TypeError("figure-relevance proposal is unsupported")
        value_validation._require_tuple("selection warnings", self.warnings)
        value_validation._require_tuple("selection failures", self.failures)
        if any(
            not isinstance(item, FigureRelevanceWarning)
            for item in self.warnings
        ) or any(
            not isinstance(item, FigureRelevanceFailure)
            for item in self.failures
        ):
            raise TypeError("selection result contains an unsupported value")
        if len(self.warnings) > _MAX_WARNINGS_PER_SELECTION:
            raise FigureRelevanceLimitError("too many selection warnings")
        if len(self.failures) > _MAX_FAILURES_PER_SELECTION:
            raise FigureRelevanceLimitError("too many selection failures")
        if any(
            item.selection_id != self.selection_id for item in self.warnings
        ):
            raise ValueError("warning selection identity is inconsistent")
        if any(
            item.selection_id != self.selection_id for item in self.failures
        ):
            raise ValueError("failure selection identity is inconsistent")
        if self.proposal is not None and (
            self.proposal.selection_id != self.selection_id
            or self.proposal.candidate_id != self.candidate_id
        ):
            raise ValueError("proposal selection identity is inconsistent")
        if (
            self.proposal is not None
            and self.proposal.confidence is None
            and not self.warnings
        ):
            raise ValueError(
                "unavailable proposal confidence requires a warning"
            )
        if self.status is FigureRelevanceStatus.COMPLETED:
            if self.proposal is None or self.failures:
                raise ValueError(
                    "completed relevance requires one proposal and no failures"
                )
        elif self.status is FigureRelevanceStatus.PARTIAL:
            if self.proposal is None or not self.failures:
                raise ValueError(
                    "partial relevance requires a proposal and failure"
                )
        elif self.proposal is not None or not self.failures:
            raise ValueError(
                "failed relevance requires failure without proposal"
            )
        warning_ids = tuple(item.warning_id for item in self.warnings)
        failure_ids = tuple(item.failure_id for item in self.failures)
        if len(set(warning_ids)) != len(warning_ids):
            raise ValueError("selection warning IDs must be unique")
        if len(set(failure_ids)) != len(failure_ids):
            raise ValueError("selection failure IDs must be unique")
        expected = selection_identity._selection_result_id(
            self.selection_id,
            self.candidate_id,
            self.status,
            self.proposal,
            self.warnings,
            self.failures,
        )
        if self.selection_result_id != expected:
            raise ValueError(
                "figure-relevance selection-result ID is inconsistent"
            )

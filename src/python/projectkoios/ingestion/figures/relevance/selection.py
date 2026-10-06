"""Figure-relevance candidate selection."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.figures import (
    FigureCandidate,
    FigureDetectionResult,
)
from projectkoios.ingestion.figures.relevance.constants import (
    FIGURE_RELEVANCE_CONTRACT_VERSION,
)
from projectkoios.ingestion.figures.relevance.validation import (
    selection as selection_validation,
)
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True)
class FigureRelevanceSelection:
    selection_id: str
    detection_result: FigureDetectionResult
    candidate_id: str
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        detection_result: FigureDetectionResult,
        candidate_id: str,
    ) -> FigureRelevanceSelection:
        candidate = selection_validation._selected_candidate(
            detection_result, candidate_id
        )
        return cls(
            selection_id=stable_id(
                "figure-relevance-selection",
                detection_result.result_id,
                candidate.candidate_id,
            ),
            detection_result=detection_result,
            candidate_id=candidate_id,
        )

    @property
    def candidate(self) -> FigureCandidate:
        return selection_validation._selected_candidate(
            self.detection_result, self.candidate_id
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError("unsupported figure-relevance selection version")
        if not isinstance(self.detection_result, FigureDetectionResult):
            raise TypeError("selection requires a figure detection result")
        candidate = selection_validation._selected_candidate(
            self.detection_result, self.candidate_id
        )
        expected = stable_id(
            "figure-relevance-selection",
            self.detection_result.result_id,
            candidate.candidate_id,
        )
        if self.selection_id != expected:
            raise ValueError("figure-relevance selection ID is inconsistent")

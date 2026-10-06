"""Figure-relevance action request."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.figures.relevance.configuration import (
    FigureRelevanceConfiguration,
)
from projectkoios.ingestion.figures.relevance.constants import (
    FIGURE_RELEVANCE_CONTRACT_VERSION,
)
from projectkoios.ingestion.figures.relevance.identity import (
    request as request_identity,
)
from projectkoios.ingestion.figures.relevance.selection import (
    FigureRelevanceSelection,
)
from projectkoios.ingestion.figures.relevance.validation import (
    request as request_validation,
)


@dataclass(frozen=True)
class FigureRelevanceRequest(DataObjectActionRequest):
    request_id: str
    review_question: str
    selections: tuple[FigureRelevanceSelection, ...]
    configuration: FigureRelevanceConfiguration
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        review_question: str,
        selections: tuple[FigureRelevanceSelection, ...],
        configuration: FigureRelevanceConfiguration | None = None,
    ) -> FigureRelevanceRequest:
        actual = configuration or FigureRelevanceConfiguration()
        request_validation._validate_request_parts(
            review_question, selections, actual
        )
        return cls(
            request_id=request_identity._request_id(
                review_question, selections, actual
            ),
            review_question=review_question,
            selections=selections,
            configuration=actual,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError("unsupported figure-relevance request version")
        request_validation._validate_request_parts(
            self.review_question, self.selections, self.configuration
        )
        if self.request_id != request_identity._request_id(
            self.review_question, self.selections, self.configuration
        ):
            raise ValueError("figure-relevance request ID is inconsistent")

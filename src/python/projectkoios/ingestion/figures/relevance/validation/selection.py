"""Figure-relevance selection validation."""

from __future__ import annotations

from projectkoios.ingestion.figures import (
    FigureCandidate,
    FigureDetectionResult,
)
from projectkoios.ingestion.figures.relevance.validation import (
    value as value_validation,
)


def _selected_candidate(
    detection_result: FigureDetectionResult,
    candidate_id: str,
) -> FigureCandidate:
    value_validation._bounded_string(
        "candidate ID", candidate_id, nonempty=True
    )
    matches = tuple(
        candidate
        for candidate in detection_result.candidates
        if candidate.candidate_id == candidate_id
    )
    if len(matches) != 1:
        raise ValueError(
            "figure-relevance selection must resolve one exact candidate"
        )
    return matches[0]

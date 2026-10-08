"""Exact equation review and chunk-text gate."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)


@dataclass(frozen=True, slots=True)
class ReadingEquationGate:
    """Bind evidence review state to explicit chunk-text eligibility."""

    review_status: ReadingReviewStatus
    accepted: bool
    review_required: bool
    chunk_text_eligible: bool

    def __post_init__(self) -> None:
        if not isinstance(self.review_status, ReadingReviewStatus):
            raise TypeError("review_status must be ReadingReviewStatus")
        states = (self.accepted, self.review_required, self.chunk_text_eligible)
        if any(type(value) is not bool for value in states):
            raise TypeError("equation gate states must be booleans")
        if self.review_status is ReadingReviewStatus.UNREVIEWED:
            if (
                self.accepted
                or not self.review_required
                or self.chunk_text_eligible
            ):
                raise ReadingEvidenceError(
                    "unreviewed equation gate state is inconsistent"
                )
        elif self.review_status is ReadingReviewStatus.ACCEPTED:
            if not self.accepted or self.review_required:
                raise ReadingEvidenceError(
                    "accepted equation gate state is inconsistent"
                )
        elif self.accepted or self.review_required or self.chunk_text_eligible:
            raise ReadingEvidenceError(
                "rejected equation gate state is inconsistent"
            )

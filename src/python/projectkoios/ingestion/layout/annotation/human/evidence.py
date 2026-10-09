"""Optional terminal human review over one exact model resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.annotation.collection import (
    LayoutAnnotationCollection,
)
from projectkoios.ingestion.layout.annotation.kind import (
    LayoutAnnotationOutcome,
)
from projectkoios.ingestion.layout.annotation.model.resolution.result import (
    LayoutModelAnnotationResolutionResult,
    LayoutModelAnnotationResolutionStatus,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


class LayoutHumanFinalReviewStatus(StrEnum):
    """Explicit state of optional terminal human review."""

    NOT_HUMAN_REVIEWED = "not_human_reviewed"
    AFFIRMED = "affirmed"
    CORRECTED = "corrected"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class LayoutHumanFinalReviewEvidence(AbstractImmutableDataObject):
    """Bind optional human judgment to one exact admitted model resolution.

    This append-only evidence neither rewrites model output nor authorizes
    publication.
    """

    CONTRACT_NAME: ClassVar[str] = "layout-human-final-review-evidence"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    resolution: LayoutModelAnnotationResolutionResult
    status: LayoutHumanFinalReviewStatus
    reviewer_id: str | None = None
    review_protocol_id: str | None = None
    correction: LayoutAnnotationCollection | None = None
    review_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.resolution) is not LayoutModelAnnotationResolutionResult:
            raise TypeError(
                "resolution must be LayoutModelAnnotationResolutionResult"
            )
        if self.resolution.status is not (
            LayoutModelAnnotationResolutionStatus.ADMITTED
        ):
            raise ValueError(
                "human final review requires an admitted resolution"
            )
        if not isinstance(self.status, LayoutHumanFinalReviewStatus):
            raise TypeError("status must be LayoutHumanFinalReviewStatus")
        if self.status is LayoutHumanFinalReviewStatus.NOT_HUMAN_REVIEWED:
            if (
                self.reviewer_id is not None
                or self.review_protocol_id is not None
                or self.correction is not None
            ):
                raise ValueError(
                    "not-reviewed evidence cannot claim a human decision"
                )
        else:
            reviewer = LayoutValueValidation.require_text(
                "reviewer_id", self.reviewer_id
            )
            LayoutValueValidation.require_text(
                "review_protocol_id", self.review_protocol_id
            )
            if self.status is LayoutHumanFinalReviewStatus.CORRECTED:
                if (
                    type(self.correction) is not LayoutAnnotationCollection
                    or self.correction.case_id != self.resolution.case_id
                    or self.correction.annotator_id != reviewer
                    or self.correction.outcome
                    is not LayoutAnnotationOutcome.CORRECTION_PROPOSED
                ):
                    raise ValueError(
                        "corrected review requires a reviewer-authored "
                        "case-bound correction"
                    )
            elif self.correction is not None:
                raise ValueError(
                    "only corrected review may carry correction evidence"
                )
        object.__setattr__(
            self,
            "review_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.resolution.result_id,
                self.status,
                self.reviewer_id,
                self.review_protocol_id,
                None
                if self.correction is None
                else self.correction.annotation_id,
            ),
        )

    @property
    def is_terminal(self) -> bool:
        """Return whether a human supplied a terminal judgment."""
        return (
            self.status is not LayoutHumanFinalReviewStatus.NOT_HUMAN_REVIEWED
        )

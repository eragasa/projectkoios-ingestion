"""Structurally valid model-authored layout annotation candidate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.annotation.failure import (
    LayoutFailureAnnotation,
)
from projectkoios.ingestion.layout.annotation.kind import (
    LayoutAnnotationOutcome,
)
from projectkoios.ingestion.layout.annotation.order import (
    LayoutReadingOrderAnnotation,
)
from projectkoios.ingestion.layout.annotation.region import (
    LayoutRegionAnnotation,
)
from projectkoios.ingestion.layout.annotation.validation import (
    LayoutAnnotationValidation,
)
from projectkoios.ingestion.layout.review.result import LayoutReviewCase


@dataclass(frozen=True, slots=True)
class LayoutModelAnnotationCandidate(AbstractImmutableDataObject):
    """Retain parsed model evidence without claiming human authorship."""

    CONTRACT_NAME: ClassVar[str] = "layout-model-annotation-candidate"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    case: LayoutReviewCase
    outcome: LayoutAnnotationOutcome
    regions: tuple[LayoutRegionAnnotation, ...]
    order_edges: tuple[LayoutReadingOrderAnnotation, ...]
    failures: tuple[LayoutFailureAnnotation, ...]
    candidate_id: str = field(init=False)

    def __post_init__(self) -> None:
        LayoutAnnotationValidation.validate(
            case=self.case,
            outcome=self.outcome,
            regions=self.regions,
            order_edges=self.order_edges,
            failures=self.failures,
        )
        object.__setattr__(
            self,
            "candidate_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.case.case_id,
                self.outcome,
                tuple(
                    sorted(item.region_annotation_id for item in self.regions)
                ),
                tuple(
                    sorted(
                        item.order_annotation_id for item in self.order_edges
                    )
                ),
                tuple(
                    sorted(item.failure_annotation_id for item in self.failures)
                ),
            ),
        )

    @property
    def case_id(self) -> str:
        """Return the exact review case interpreted by the model."""
        return self.case.case_id

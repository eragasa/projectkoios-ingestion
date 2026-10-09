"""Complete immutable human layout annotation collection."""

from __future__ import annotations

from dataclasses import dataclass
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
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class LayoutAnnotationCollection(AbstractImmutableDataObject):
    """Bind human observations and corrections to one exact review case.

    This record is annotation evidence. It does not accept a proposal, replace
    ``PageLayoutResult``, or authorize downstream publication.
    """

    CONTRACT_NAME: ClassVar[str] = "layout-annotation-collection"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    annotation_id: str
    case: LayoutReviewCase
    annotator_id: str
    outcome: LayoutAnnotationOutcome
    regions: tuple[LayoutRegionAnnotation, ...]
    order_edges: tuple[LayoutReadingOrderAnnotation, ...]
    failures: tuple[LayoutFailureAnnotation, ...]
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        case: LayoutReviewCase,
        annotator_id: str,
        outcome: LayoutAnnotationOutcome,
        regions: tuple[LayoutRegionAnnotation, ...] = (),
        order_edges: tuple[LayoutReadingOrderAnnotation, ...] = (),
        failures: tuple[LayoutFailureAnnotation, ...] = (),
    ) -> LayoutAnnotationCollection:
        """Create one validated annotation collection for an exact case."""
        annotator = LayoutValueValidation.require_text(
            "annotator_id", annotator_id
        )
        LayoutAnnotationValidation.validate(
            case=case,
            outcome=outcome,
            regions=regions,
            order_edges=order_edges,
            failures=failures,
        )
        annotation_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            case.case_id,
            annotator,
            outcome,
            tuple(region.region_annotation_id for region in regions),
            tuple(edge.order_annotation_id for edge in order_edges),
            tuple(failure.failure_annotation_id for failure in failures),
        )
        return cls(
            annotation_id=annotation_id,
            case=case,
            annotator_id=annotator,
            outcome=outcome,
            regions=regions,
            order_edges=order_edges,
            failures=failures,
        )

    @property
    def case_id(self) -> str:
        """Return the exact review-case identity being annotated."""
        return self.case.case_id

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout annotation contract")
        LayoutValueValidation.require_text("annotator_id", self.annotator_id)
        LayoutAnnotationValidation.validate(
            case=self.case,
            outcome=self.outcome,
            regions=self.regions,
            order_edges=self.order_edges,
            failures=self.failures,
        )
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.case.case_id,
            self.annotator_id,
            self.outcome,
            tuple(region.region_annotation_id for region in self.regions),
            tuple(edge.order_annotation_id for edge in self.order_edges),
            tuple(failure.failure_annotation_id for failure in self.failures),
        )
        if self.annotation_id != expected:
            raise ValueError("layout annotation ID is inconsistent")

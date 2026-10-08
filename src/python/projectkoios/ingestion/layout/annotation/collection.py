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
from projectkoios.ingestion.layout.annotation.limits.definition import (
    MAX_LAYOUT_ANNOTATIONS_PER_KIND,
)
from projectkoios.ingestion.layout.annotation.limits.error import (
    LayoutAnnotationLimitError,
)
from projectkoios.ingestion.layout.annotation.order import (
    LayoutReadingOrderAnnotation,
    LayoutReadingOrderValidation,
)
from projectkoios.ingestion.layout.annotation.region import (
    LayoutRegionAnnotation,
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
        cls.validate(
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

    @classmethod
    def validate(
        cls,
        *,
        case: LayoutReviewCase,
        outcome: LayoutAnnotationOutcome,
        regions: tuple[LayoutRegionAnnotation, ...],
        order_edges: tuple[LayoutReadingOrderAnnotation, ...],
        failures: tuple[LayoutFailureAnnotation, ...],
    ) -> None:
        """Validate references, bounds, outcomes, and order acyclicity."""
        if type(case) is not LayoutReviewCase:
            raise TypeError("case must be LayoutReviewCase")
        if not isinstance(outcome, LayoutAnnotationOutcome):
            raise TypeError("outcome must be LayoutAnnotationOutcome")
        collections = (
            (
                "regions",
                regions,
                LayoutRegionAnnotation,
                "region_annotation_id",
            ),
            (
                "order_edges",
                order_edges,
                LayoutReadingOrderAnnotation,
                "order_annotation_id",
            ),
            (
                "failures",
                failures,
                LayoutFailureAnnotation,
                "failure_annotation_id",
            ),
        )
        for name, values, expected_type, identity_name in collections:
            if not isinstance(values, tuple) or any(
                type(value) is not expected_type for value in values
            ):
                raise TypeError(f"{name} contains an invalid annotation")
            if len(values) > MAX_LAYOUT_ANNOTATIONS_PER_KIND:
                raise LayoutAnnotationLimitError(
                    f"{name} exceeds annotation implementation limit"
                )
            identities = [getattr(value, identity_name) for value in values]
            if name != "order_edges" and len(set(identities)) != len(
                identities
            ):
                raise ValueError(f"{name} identities must be unique")
            if any(value.case_id != case.case_id for value in values):
                raise ValueError(f"{name} references another review case")

        valid_block_ids = {review.block_id for review in case.block_reviews}
        valid_proposal_ids = set(case.proposal_ids)
        valid_region_ids = {region.region_annotation_id for region in regions}
        for region in regions:
            if not set(region.block_ids) <= valid_block_ids:
                raise ValueError("region references an unknown native block")
            x1, y1, x2, y2 = region.bounding_box_pixels
            if (
                x1 < 0.0
                or y1 < 0.0
                or x2 > case.image_width
                or y2 > case.image_height
            ):
                raise ValueError("region annotation exceeds render bounds")
        for failure in failures:
            if not set(failure.block_ids) <= valid_block_ids:
                raise ValueError("failure references an unknown native block")
            if not set(failure.proposal_ids) <= valid_proposal_ids:
                raise ValueError("failure references an unknown proposal")
            if not set(failure.region_annotation_ids) <= valid_region_ids:
                raise ValueError(
                    "failure references an unknown region annotation"
                )
        LayoutReadingOrderValidation.validate(
            valid_block_ids=valid_block_ids,
            edges=order_edges,
        )

        if outcome is LayoutAnnotationOutcome.NO_FAILURE_OBSERVED and (
            regions or order_edges or failures
        ):
            raise ValueError("no-failure outcome cannot carry corrections")
        if outcome is LayoutAnnotationOutcome.FAILURE_OBSERVED and not failures:
            raise ValueError("failure outcome requires a failure annotation")
        if outcome is LayoutAnnotationOutcome.CORRECTION_PROPOSED and not (
            regions or order_edges
        ):
            raise ValueError("correction outcome requires corrected evidence")

    @property
    def case_id(self) -> str:
        """Return the exact review-case identity being annotated."""
        return self.case.case_id

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout annotation contract")
        LayoutValueValidation.require_text("annotator_id", self.annotator_id)
        self.validate(
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

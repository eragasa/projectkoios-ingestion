"""Shared structural validation for layout annotation evidence."""

from __future__ import annotations

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


class LayoutAnnotationValidation:
    """Validate evidence-author-neutral layout annotation components."""

    __slots__ = ()

    @staticmethod
    def validate(
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

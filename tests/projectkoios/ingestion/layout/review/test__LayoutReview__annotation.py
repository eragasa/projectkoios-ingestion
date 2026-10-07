from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.layout.annotation.collection import (
    LayoutAnnotationCollection,
)
from projectkoios.ingestion.layout.annotation.failure import (
    LayoutFailureAnnotation,
)
from projectkoios.ingestion.layout.annotation.kind import (
    LayoutAnnotationOutcome,
    LayoutFailureKind,
)
from projectkoios.ingestion.layout.annotation.limits.definition import (
    MAX_LAYOUT_REFERENCES_PER_ANNOTATION,
)
from projectkoios.ingestion.layout.annotation.limits.error import (
    LayoutAnnotationLimitError,
)
from projectkoios.ingestion.layout.annotation.order import (
    LayoutReadingOrderAnnotation,
)
from projectkoios.ingestion.layout.annotation.region import (
    LayoutRegionAnnotation,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind

from tests.projectkoios.ingestion.layout.review.layout_review_support import (
    LayoutReviewFixture,
)

FIXTURE = LayoutReviewFixture()


def test__layout_annotation__records_correction_without_accepting_it() -> None:
    page, adapter_result, _, review_case = FIXTURE.prepared_case()
    region = LayoutRegionAnnotation.create(
        case_id=review_case.case_id,
        kind=LayoutRegionKind.TEXT,
        bounding_box_pixels=(20.0, 20.0, 80.0, 100.0),
        block_ids=tuple(block.block_id for block in page.blocks),
    )
    order = LayoutReadingOrderAnnotation.create(
        case_id=review_case.case_id,
        before_block_id=page.blocks[0].block_id,
        after_block_id=page.blocks[1].block_id,
    )
    failure = LayoutFailureAnnotation.create(
        case_id=review_case.case_id,
        kind=LayoutFailureKind.MISSED_REGION,
        block_ids=(page.blocks[1].block_id,),
        proposal_ids=(adapter_result.proposals[0].proposal_id,),
        region_annotation_ids=(region.region_annotation_id,),
    )

    annotation = LayoutAnnotationCollection.create(
        case=review_case,
        annotator_id="fixture-annotator",
        outcome=LayoutAnnotationOutcome.CORRECTION_PROPOSED,
        regions=(region,),
        order_edges=(order,),
        failures=(failure,),
    )

    assert annotation.case_id == review_case.case_id
    assert annotation.outcome is LayoutAnnotationOutcome.CORRECTION_PROPOSED
    assert annotation.failures == (failure,)
    replayed = LayoutAnnotationCollection.create(
        case=review_case,
        annotator_id="fixture-annotator",
        outcome=LayoutAnnotationOutcome.CORRECTION_PROPOSED,
        regions=(region,),
        order_edges=(order,),
        failures=(failure,),
    )
    assert CanonicalJsonSerializer.serialize_text(
        annotation
    ) == CanonicalJsonSerializer.serialize_text(replayed)
    with pytest.raises(FrozenInstanceError):
        annotation.annotator_id = "changed"  # type: ignore[misc]


def test__layout_annotation__rejects_cyclic_order() -> None:
    page, _, _, review_case = FIXTURE.prepared_case()
    forward = LayoutReadingOrderAnnotation.create(
        case_id=review_case.case_id,
        before_block_id=page.blocks[0].block_id,
        after_block_id=page.blocks[1].block_id,
    )
    backward = LayoutReadingOrderAnnotation.create(
        case_id=review_case.case_id,
        before_block_id=page.blocks[1].block_id,
        after_block_id=page.blocks[0].block_id,
    )

    with pytest.raises(ValueError, match="cycle"):
        LayoutAnnotationCollection.create(
            case=review_case,
            annotator_id="fixture-annotator",
            outcome=LayoutAnnotationOutcome.CORRECTION_PROPOSED,
            order_edges=(forward, backward),
        )


@pytest.mark.parametrize(
    ("reference_count", "accepted"),
    (
        # The exact per-annotation reference boundary remains valid.
        (MAX_LAYOUT_REFERENCES_PER_ANNOTATION, True),
        # One additional affected identity is rejected before stable hashing.
        (MAX_LAYOUT_REFERENCES_PER_ANNOTATION + 1, False),
    ),
)
def test__layout_failure_annotation__bounds_affected_references(
    reference_count: int,
    accepted: bool,
) -> None:
    _, _, _, review_case = FIXTURE.prepared_case()
    block_ids = tuple(
        f"fixture-block:{index:05d}" for index in range(reference_count)
    )
    if accepted:
        annotation = LayoutFailureAnnotation.create(
            case_id=review_case.case_id,
            kind=LayoutFailureKind.OTHER,
            block_ids=block_ids,
        )
        assert len(annotation.block_ids) == reference_count
    else:
        with pytest.raises(LayoutAnnotationLimitError):
            LayoutFailureAnnotation.create(
                case_id=review_case.case_id,
                kind=LayoutFailureKind.OTHER,
                block_ids=block_ids,
            )


def test__layout_annotation__rejects_duplicate_order_endpoints() -> None:
    page, _, _, review_case = FIXTURE.prepared_case()
    edge = LayoutReadingOrderAnnotation.create(
        case_id=review_case.case_id,
        before_block_id=page.blocks[0].block_id,
        after_block_id=page.blocks[1].block_id,
    )

    with pytest.raises(ValueError, match="endpoint pairs"):
        LayoutAnnotationCollection.create(
            case=review_case,
            annotator_id="fixture-annotator",
            outcome=LayoutAnnotationOutcome.CORRECTION_PROPOSED,
            order_edges=(edge, edge),
        )

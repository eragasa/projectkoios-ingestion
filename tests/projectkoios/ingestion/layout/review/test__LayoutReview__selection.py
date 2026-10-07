from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.proposal.region import LayoutRegionProposal
from projectkoios.ingestion.layout.review.actionizer import (
    DeterministicLayoutReviewActionizer,
)
from projectkoios.ingestion.layout.review.block import (
    LayoutBlockReviewEvidence,
)
from projectkoios.ingestion.layout.review.configuration import (
    LayoutReviewConfiguration,
)
from projectkoios.ingestion.layout.review.kind import (
    LayoutBlockReviewStatus,
    LayoutReviewReason,
)
from projectkoios.ingestion.layout.review.limits.definition import (
    MAX_LAYOUT_REVIEW_COMPARISONS,
)
from projectkoios.ingestion.layout.review.limits.error import (
    LayoutReviewLimitError,
)
from projectkoios.ingestion.layout.review.overlap import (
    LayoutBlockRegionOverlap,
)
from projectkoios.ingestion.layout.review.request import LayoutReviewRequest

from tests.projectkoios.ingestion.layout.review.layout_review_support import (
    LayoutReviewFixture,
)

FIXTURE = LayoutReviewFixture()


def test__layout_review__selects_incomplete_region_coverage() -> None:
    page, _, request, review_case = FIXTURE.prepared_case()

    assert review_case.covered_block_ids == (page.blocks[0].block_id,)
    assert review_case.uncovered_block_ids == (page.blocks[1].block_id,)
    assert review_case.invalid_geometry_block_ids == ()
    assert review_case.page_coverage_ratio == 0.5
    assert review_case.reasons == (
        LayoutReviewReason.INCOMPLETE_REGION_COVERAGE,
    )
    assert review_case.requires_review is True
    replayed = DeterministicLayoutReviewActionizer().action(request=request)
    assert review_case == replayed
    assert CanonicalJsonSerializer.serialize_text(
        review_case
    ) == CanonicalJsonSerializer.serialize_text(replayed)


def test__layout_review_request__rejects_excessive_comparisons() -> None:
    _, adapter_result, request, _ = FIXTURE.prepared_case()
    exact_configuration = LayoutReviewConfiguration(
        max_comparisons=2,
    )
    assert (
        LayoutReviewRequest.create(
            layout=request.layout,
            render=request.render,
            proposal_source=adapter_result.proposal_source,
            proposals=adapter_result.proposals,
            configuration=exact_configuration,
        ).configuration.max_comparisons
        == 2
    )

    with pytest.raises(LayoutReviewLimitError, match="max_comparisons"):
        LayoutReviewRequest.create(
            layout=request.layout,
            render=request.render,
            proposal_source=adapter_result.proposal_source,
            proposals=adapter_result.proposals,
            configuration=LayoutReviewConfiguration(max_comparisons=1),
        )


def test__layout_review__handles_maximum_comparison_bound() -> None:
    request = FIXTURE.maximum_comparison_request()

    assert (
        len(request.layout.input_text_blocks) * len(request.proposals)
        == MAX_LAYOUT_REVIEW_COMPARISONS
    )
    case = DeterministicLayoutReviewActionizer().action(request=request)
    assert len(case.block_reviews) == len(request.layout.input_text_blocks)
    assert case.overlaps == ()
    assert case.covered_block_ids == ()


def test__layout_review_action__rejects_excessive_derived_overlaps() -> None:
    _, adapter_result, request, _ = FIXTURE.prepared_case()
    covering_proposal = LayoutRegionProposal.create(
        render_id=request.render.render_id,
        proposal_source_id=adapter_result.proposal_source.proposal_source_id,
        kind=LayoutRegionKind.TEXT,
        bounding_box_pixels=(20.0, 20.0, 80.0, 100.0),
        confidence=1.0,
    )
    bounded_request = LayoutReviewRequest.create(
        layout=request.layout,
        render=request.render,
        proposal_source=adapter_result.proposal_source,
        proposals=(covering_proposal,),
        configuration=LayoutReviewConfiguration(
            max_comparisons=2,
            max_overlaps=1,
        ),
    )

    with pytest.raises(LayoutReviewLimitError, match="max_overlaps"):
        DeterministicLayoutReviewActionizer().action(request=bounded_request)


def test__layout_review_case__rejects_reordered_and_substituted_overlaps() -> (
    None
):
    _, adapter_result, request, _ = FIXTURE.prepared_case()
    proposals = (
        LayoutRegionProposal.create(
            render_id=request.render.render_id,
            proposal_source_id=(
                adapter_result.proposal_source.proposal_source_id
            ),
            kind=kind,
            bounding_box_pixels=box,
            confidence=confidence,
        )
        for kind, box, confidence in (
            (LayoutRegionKind.TEXT, (20.0, 20.0, 80.0, 40.0), 0.9),
            (LayoutRegionKind.TABLE, (20.0, 20.0, 70.0, 40.0), 0.8),
        )
    )
    bounded_request = LayoutReviewRequest.create(
        layout=request.layout,
        render=request.render,
        proposal_source=adapter_result.proposal_source,
        proposals=tuple(proposals),
        configuration=LayoutReviewConfiguration(
            max_comparisons=4,
            max_overlaps=4,
        ),
    )
    case = DeterministicLayoutReviewActionizer().action(request=bounded_request)
    covered = case.block_reviews[0]
    assert len(covered.overlaps) == 2

    with pytest.raises(ValueError, match="overlap IDs must be unique"):
        LayoutBlockReviewEvidence.create(
            render_id=covered.render_id,
            mapping_id=covered.mapping_id,
            block_id=covered.block_id,
            block_bounding_box_pixels=covered.block_bounding_box_pixels,
            status=covered.status,
            overlaps=(covered.overlaps[0], covered.overlaps[0]),
            significant_proposal_ids=(covered.overlaps[0].proposal_id,),
        )

    reordered = LayoutBlockReviewEvidence.create(
        render_id=covered.render_id,
        mapping_id=covered.mapping_id,
        block_id=covered.block_id,
        block_bounding_box_pixels=covered.block_bounding_box_pixels,
        status=covered.status,
        overlaps=tuple(reversed(covered.overlaps)),
        significant_proposal_ids=tuple(
            reversed(covered.significant_proposal_ids)
        ),
    )
    with pytest.raises(ValueError, match="incomplete or altered"):
        replace(case, block_reviews=(reordered, *case.block_reviews[1:]))

    foreign_proposal = LayoutRegionProposal.create(
        render_id=request.render.render_id,
        proposal_source_id=adapter_result.proposal_source.proposal_source_id,
        kind=LayoutRegionKind.FIGURE,
        bounding_box_pixels=(20.0, 20.0, 60.0, 40.0),
        confidence=0.7,
    )
    assert covered.block_bounding_box_pixels is not None
    foreign_overlap = LayoutBlockRegionOverlap.measure(
        block_id=covered.block_id,
        block_bounding_box_pixels=covered.block_bounding_box_pixels,
        proposal=foreign_proposal,
        render=request.render,
    )
    assert foreign_overlap is not None
    substituted = LayoutBlockReviewEvidence.create(
        render_id=covered.render_id,
        mapping_id=covered.mapping_id,
        block_id=covered.block_id,
        block_bounding_box_pixels=covered.block_bounding_box_pixels,
        status=covered.status,
        overlaps=(covered.overlaps[0], foreign_overlap),
        significant_proposal_ids=(
            covered.overlaps[0].proposal_id,
            foreign_overlap.proposal_id,
        ),
    )
    with pytest.raises(ValueError, match="incomplete or altered"):
        replace(case, block_reviews=(substituted, *case.block_reviews[1:]))


def test__layout_review_case__rejects_omitted_positive_overlap() -> None:
    _, _, _, review_case = FIXTURE.prepared_case()
    covered = review_case.block_reviews[0]
    altered = LayoutBlockReviewEvidence.create(
        render_id=covered.render_id,
        mapping_id=covered.mapping_id,
        block_id=covered.block_id,
        block_bounding_box_pixels=covered.block_bounding_box_pixels,
        status=LayoutBlockReviewStatus.UNCOVERED,
        overlaps=(),
        significant_proposal_ids=(),
    )

    with pytest.raises(ValueError, match="incomplete or altered"):
        replace(
            review_case,
            block_reviews=(altered, *review_case.block_reviews[1:]),
        )


def test__layout_review_contracts__reject_stale_identities() -> None:
    _, _, _, review_case = FIXTURE.prepared_case()

    with pytest.raises(ValueError, match="inconsistent"):
        replace(review_case, case_id="layout-review-case:sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="inconsistent"):
        replace(
            review_case.block_reviews[0],
            block_review_id="layout-block-review:sha256:" + "0" * 64,
        )

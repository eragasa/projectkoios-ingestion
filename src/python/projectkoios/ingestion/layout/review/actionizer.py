"""Deterministic preparation of layout failure-review cases."""

from __future__ import annotations

from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.layout.contracts import LayoutPageKind
from projectkoios.ingestion.layout.review.configuration import (
    LayoutReviewConfiguration,
)
from projectkoios.ingestion.layout.review.kind import LayoutReviewReason
from projectkoios.ingestion.layout.review.limits.error import (
    LayoutReviewLimitError,
)
from projectkoios.ingestion.layout.review.overlap import (
    LayoutBlockRegionOverlap,
)
from projectkoios.ingestion.layout.review.request import LayoutReviewRequest
from projectkoios.ingestion.layout.review.result import LayoutReviewCase


class DeterministicLayoutReviewActionizer(
    ConfigurableDataObjectActionizer[
        LayoutReviewConfiguration,
        LayoutReviewRequest,
        LayoutReviewCase,
    ]
):
    """Compare baseline and region proposals without accepting either."""

    __slots__ = ()

    actionizer_name = "deterministic-layout-review-preparation"
    actionizer_version = "1"
    configuration_type = LayoutReviewConfiguration

    def action(self, *, request: LayoutReviewRequest) -> LayoutReviewCase:
        """Prepare one bounded immutable review case."""
        if type(request) is not LayoutReviewRequest:
            raise TypeError("request must be LayoutReviewRequest")
        configuration = request.configuration
        if type(configuration) is not LayoutReviewConfiguration:
            raise TypeError("action configuration contract differs")

        overlaps: list[LayoutBlockRegionOverlap] = []
        invalid_geometry: list[str] = []
        for block in request.layout.input_text_blocks:
            if block.bounding_box is None:
                invalid_geometry.append(block.block_id)
                continue
            for proposal in request.proposals:
                overlap = LayoutBlockRegionOverlap.measure(
                    block=block,
                    proposal=proposal,
                    render=request.render,
                    page_width=request.layout.page_width,
                    page_height=request.layout.page_height,
                )
                if overlap is None:
                    continue
                overlaps.append(overlap)
                if len(overlaps) > configuration.max_overlaps:
                    raise LayoutReviewLimitError(
                        "derived overlaps exceed max_overlaps"
                    )

        significant = tuple(
            overlap
            for overlap in overlaps
            if overlap.intersection_over_block_area
            >= configuration.minimum_block_intersection_ratio
        )
        covered = tuple(
            block.block_id
            for block in request.layout.input_text_blocks
            if any(
                overlap.block_id == block.block_id for overlap in significant
            )
        )
        invalid = tuple(invalid_geometry)
        uncovered = tuple(
            block.block_id
            for block in request.layout.input_text_blocks
            if block.block_id not in covered and block.block_id not in invalid
        )
        block_count = len(request.layout.input_text_blocks)
        coverage_ratio = (
            1.0 if block_count == 0 else round(len(covered) / block_count, 12)
        )

        reasons: set[LayoutReviewReason] = set()
        if request.layout.page_kind is LayoutPageKind.AMBIGUOUS:
            reasons.add(LayoutReviewReason.BASELINE_AMBIGUOUS)
        if request.layout.warnings:
            reasons.add(LayoutReviewReason.BASELINE_WARNING)
        if invalid:
            reasons.add(LayoutReviewReason.INVALID_BLOCK_GEOMETRY)
        if block_count and not request.proposals:
            reasons.add(LayoutReviewReason.NO_REGION_PROPOSALS)
        if (
            block_count
            and coverage_ratio < configuration.minimum_page_coverage_ratio
        ):
            reasons.add(LayoutReviewReason.INCOMPLETE_REGION_COVERAGE)

        proposal_kind = {
            proposal.proposal_id: proposal.kind
            for proposal in request.proposals
        }
        for block_id in covered:
            kinds = {
                proposal_kind[overlap.proposal_id]
                for overlap in significant
                if overlap.block_id == block_id
            }
            if len(kinds) > 1:
                reasons.add(LayoutReviewReason.CONFLICTING_REGION_KINDS)
                break

        return LayoutReviewCase.create(
            request=request,
            overlaps=tuple(overlaps),
            covered_block_ids=covered,
            uncovered_block_ids=uncovered,
            invalid_geometry_block_ids=invalid,
            page_coverage_ratio=coverage_ratio,
            reasons=tuple(sorted(reasons, key=str)),
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )

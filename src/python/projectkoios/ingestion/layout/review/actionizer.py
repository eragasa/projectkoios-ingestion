"""Deterministic preparation of layout failure-review cases."""

from __future__ import annotations

from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.layout.review.block import (
    LayoutBlockReviewEvidence,
)
from projectkoios.ingestion.layout.review.configuration import (
    LayoutReviewConfiguration,
)
from projectkoios.ingestion.layout.review.kind import LayoutBlockReviewStatus
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
        """Prepare one bounded immutable review case in one pass per block."""
        if type(request) is not LayoutReviewRequest:
            raise TypeError("request must be LayoutReviewRequest")
        configuration = request.configuration
        if type(configuration) is not LayoutReviewConfiguration:
            raise TypeError("action configuration contract differs")

        block_reviews: list[LayoutBlockReviewEvidence] = []
        overlap_count = 0
        mapping = request.render.mapping
        for block in request.layout.input_text_blocks:
            source_box = block.bounding_box
            mapped_box = (
                None
                if source_box is None
                else mapping.source_box_to_pixel_box(source_box)
            )
            if mapped_box is not None and (
                mapped_box[0] < 0.0
                or mapped_box[1] < 0.0
                or mapped_box[2] > request.render.image_width
                or mapped_box[3] > request.render.image_height
            ):
                mapped_box = None
            if mapped_box is None:
                block_reviews.append(
                    LayoutBlockReviewEvidence.create(
                        render_id=request.render.render_id,
                        mapping_id=mapping.mapping_id,
                        block_id=block.block_id,
                        block_bounding_box_pixels=None,
                        status=LayoutBlockReviewStatus.INVALID_GEOMETRY,
                        overlaps=(),
                        significant_proposal_ids=(),
                    )
                )
                continue

            overlaps: list[LayoutBlockRegionOverlap] = []
            significant_proposal_ids: list[str] = []
            for proposal in request.proposals:
                overlap = LayoutBlockRegionOverlap.measure(
                    block_id=block.block_id,
                    block_bounding_box_pixels=mapped_box,
                    proposal=proposal,
                    render=request.render,
                )
                if overlap is None:
                    continue
                overlap_count += 1
                if overlap_count > configuration.max_overlaps:
                    raise LayoutReviewLimitError(
                        "derived overlaps exceed max_overlaps"
                    )
                overlaps.append(overlap)
                if (
                    overlap.intersection_over_block_area
                    >= configuration.minimum_block_intersection_ratio
                ):
                    significant_proposal_ids.append(proposal.proposal_id)
            significant = tuple(significant_proposal_ids)
            status = (
                LayoutBlockReviewStatus.COVERED
                if significant
                else LayoutBlockReviewStatus.UNCOVERED
            )
            block_reviews.append(
                LayoutBlockReviewEvidence.create(
                    render_id=request.render.render_id,
                    mapping_id=mapping.mapping_id,
                    block_id=block.block_id,
                    block_bounding_box_pixels=mapped_box,
                    status=status,
                    overlaps=tuple(overlaps),
                    significant_proposal_ids=significant,
                )
            )

        return LayoutReviewCase.create(
            request=request,
            block_reviews=tuple(block_reviews),
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )

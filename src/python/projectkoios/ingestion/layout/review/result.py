"""Immutable prepared layout review case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.contracts import LayoutPageKind
from projectkoios.ingestion.layout.review.block import (
    LayoutBlockReviewEvidence,
)
from projectkoios.ingestion.layout.review.kind import (
    LayoutBlockReviewStatus,
    LayoutReviewReason,
)
from projectkoios.ingestion.layout.review.limits.error import (
    LayoutReviewLimitError,
)
from projectkoios.ingestion.layout.review.overlap import (
    LayoutBlockRegionOverlap,
)
from projectkoios.ingestion.layout.review.request import LayoutReviewRequest
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class LayoutReviewCase(AbstractDataObjectActionResult):
    """Present exact baseline and proposal evidence for external annotation."""

    CONTRACT_NAME: ClassVar[str] = "layout-review-case"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    case_id: str
    request: LayoutReviewRequest
    block_reviews: tuple[LayoutBlockReviewEvidence, ...]
    page_coverage_ratio: float
    reasons: tuple[LayoutReviewReason, ...]
    requires_review: bool
    actionizer_name: str
    actionizer_version: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: LayoutReviewRequest,
        block_reviews: tuple[LayoutBlockReviewEvidence, ...],
        actionizer_name: str,
        actionizer_version: str,
    ) -> LayoutReviewCase:
        """Create one stable case from normalized per-block evidence."""
        ratio = cls.coverage_ratio_for(block_reviews)
        reasons = cls.reasons_for(
            request=request,
            block_reviews=block_reviews,
            page_coverage_ratio=ratio,
        )
        cls.validate(
            request=request,
            block_reviews=block_reviews,
            page_coverage_ratio=ratio,
            reasons=reasons,
        )
        actionizer = LayoutValueValidation.require_text(
            "actionizer_name", actionizer_name
        )
        actionizer_release = LayoutValueValidation.require_text(
            "actionizer_version", actionizer_version
        )
        case_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            request.request_id,
            tuple(review.block_review_id for review in block_reviews),
            ratio,
            reasons,
            actionizer,
            actionizer_release,
            request.configuration.configuration_id,
        )
        return cls(
            case_id=case_id,
            request=request,
            block_reviews=block_reviews,
            page_coverage_ratio=ratio,
            reasons=reasons,
            requires_review=bool(reasons),
            actionizer_name=actionizer,
            actionizer_version=actionizer_release,
        )

    @staticmethod
    def coverage_ratio_for(
        block_reviews: tuple[LayoutBlockReviewEvidence, ...],
    ) -> float:
        """Return deterministic covered-block ratio over all native blocks."""
        if not isinstance(block_reviews, tuple):
            raise TypeError("block_reviews must be a tuple")
        if not block_reviews:
            return 1.0
        covered = sum(
            review.status is LayoutBlockReviewStatus.COVERED
            for review in block_reviews
        )
        return round(covered / len(block_reviews), 12)

    @staticmethod
    def reasons_for(
        *,
        request: LayoutReviewRequest,
        block_reviews: tuple[LayoutBlockReviewEvidence, ...],
        page_coverage_ratio: float,
    ) -> tuple[LayoutReviewReason, ...]:
        """Derive review reasons from authoritative and per-block evidence."""
        reasons: set[LayoutReviewReason] = set()
        if request.layout.page_kind is LayoutPageKind.AMBIGUOUS:
            reasons.add(LayoutReviewReason.BASELINE_AMBIGUOUS)
        if request.layout.warnings:
            reasons.add(LayoutReviewReason.BASELINE_WARNING)
        if any(
            review.status is LayoutBlockReviewStatus.INVALID_GEOMETRY
            for review in block_reviews
        ):
            reasons.add(LayoutReviewReason.INVALID_BLOCK_GEOMETRY)
        if block_reviews and not request.proposals:
            reasons.add(LayoutReviewReason.NO_REGION_PROPOSALS)
        if (
            block_reviews
            and page_coverage_ratio
            < request.configuration.minimum_page_coverage_ratio
        ):
            reasons.add(LayoutReviewReason.INCOMPLETE_REGION_COVERAGE)
        proposal_kinds = {
            proposal.proposal_id: proposal.kind
            for proposal in request.proposals
        }
        if any(
            len(
                {
                    proposal_kinds[proposal_id]
                    for proposal_id in review.significant_proposal_ids
                }
            )
            > 1
            for review in block_reviews
        ):
            reasons.add(LayoutReviewReason.CONFLICTING_REGION_KINDS)
        return tuple(sorted(reasons, key=str))

    @classmethod
    def validate(
        cls,
        *,
        request: object,
        block_reviews: object,
        page_coverage_ratio: object,
        reasons: object,
    ) -> None:
        """Validate complete request-bound block evidence and derived values."""
        if type(request) is not LayoutReviewRequest:
            raise TypeError("request must be LayoutReviewRequest")
        if not isinstance(block_reviews, tuple) or any(
            type(review) is not LayoutBlockReviewEvidence
            for review in block_reviews
        ):
            raise TypeError(
                "block_reviews must contain LayoutBlockReviewEvidence"
            )
        if len(block_reviews) > request.configuration.max_blocks:
            raise LayoutReviewLimitError("block reviews exceed max_blocks")
        if (
            sum(len(review.overlaps) for review in block_reviews)
            > request.configuration.max_overlaps
        ):
            raise LayoutReviewLimitError(
                "block review overlaps exceed max_overlaps"
            )
        expected_block_ids = tuple(
            block.block_id for block in request.layout.input_text_blocks
        )
        actual_block_ids = tuple(review.block_id for review in block_reviews)
        if actual_block_ids != expected_block_ids:
            raise ValueError(
                "block reviews must match authoritative text-block order"
            )
        if len({review.block_review_id for review in block_reviews}) != len(
            block_reviews
        ):
            raise ValueError("block review identities must be unique")
        mapping_id = request.render.mapping.mapping_id
        expected_overlap_count = 0
        for block, review in zip(
            request.layout.input_text_blocks, block_reviews, strict=True
        ):
            if (
                review.render_id != request.render.render_id
                or review.mapping_id != mapping_id
            ):
                raise ValueError("block review identifies another render")
            expected_box = (
                None
                if block.bounding_box is None
                else request.render.mapping.source_box_to_pixel_box(
                    block.bounding_box
                )
            )
            if expected_box is not None and (
                expected_box[0] < 0.0
                or expected_box[1] < 0.0
                or expected_box[2] > request.render.image_width
                or expected_box[3] > request.render.image_height
            ):
                expected_box = None
            if review.block_bounding_box_pixels != expected_box:
                raise ValueError("block review pixel geometry is inconsistent")
            expected_overlaps: list[LayoutBlockRegionOverlap] = []
            if expected_box is not None:
                for proposal in request.proposals:
                    expected_overlap = LayoutBlockRegionOverlap.measure(
                        block_id=block.block_id,
                        block_bounding_box_pixels=expected_box,
                        proposal=proposal,
                        render=request.render,
                    )
                    if expected_overlap is None:
                        continue
                    expected_overlap_count += 1
                    if (
                        expected_overlap_count
                        > request.configuration.max_overlaps
                    ):
                        raise LayoutReviewLimitError(
                            "derived overlaps exceed max_overlaps"
                        )
                    expected_overlaps.append(expected_overlap)
            if review.overlaps != tuple(expected_overlaps):
                raise ValueError("overlap geometry is incomplete or altered")
            expected_significant = tuple(
                overlap.proposal_id
                for overlap in expected_overlaps
                if overlap.intersection_over_block_area
                >= request.configuration.minimum_block_intersection_ratio
            )
            if review.significant_proposal_ids != expected_significant:
                raise ValueError(
                    "significant proposal evidence is inconsistent"
                )
        ratio = LayoutValueValidation.require_ratio(
            "page_coverage_ratio", page_coverage_ratio
        )
        if ratio != cls.coverage_ratio_for(block_reviews):
            raise ValueError("page coverage ratio differs from block evidence")
        if not isinstance(reasons, tuple) or any(
            not isinstance(reason, LayoutReviewReason) for reason in reasons
        ):
            raise TypeError("reasons must contain LayoutReviewReason")
        if tuple(sorted(set(reasons), key=str)) != reasons:
            raise ValueError("reasons must be unique and sorted")
        if reasons != cls.reasons_for(
            request=request,
            block_reviews=block_reviews,
            page_coverage_ratio=ratio,
        ):
            raise ValueError("review reasons differ from block evidence")

    @property
    def request_id(self) -> str:
        """Return the complete review request identity."""
        return self.request.request_id

    @property
    def layout_result_id(self) -> str:
        """Return the authoritative layout-result identity."""
        return self.request.layout.result_id

    @property
    def render_id(self) -> str:
        """Return exact rendered-page identity."""
        return self.request.render.render_id

    @property
    def proposal_source_id(self) -> str:
        """Return proposal-source identity."""
        return self.request.proposal_source.proposal_source_id

    @property
    def proposal_ids(self) -> tuple[str, ...]:
        """Return proposal identities in request order."""
        return tuple(
            proposal.proposal_id for proposal in self.request.proposals
        )

    @property
    def image_width(self) -> int:
        """Return exact raster width."""
        return self.request.render.image_width

    @property
    def image_height(self) -> int:
        """Return exact raster height."""
        return self.request.render.image_height

    @property
    def overlaps(self) -> tuple[LayoutBlockRegionOverlap, ...]:
        """Return positive overlaps in authoritative block order."""
        return tuple(
            overlap
            for review in self.block_reviews
            for overlap in review.overlaps
        )

    @property
    def covered_block_ids(self) -> tuple[str, ...]:
        """Return covered block identities in authoritative order."""
        return tuple(
            review.block_id
            for review in self.block_reviews
            if review.status is LayoutBlockReviewStatus.COVERED
        )

    @property
    def uncovered_block_ids(self) -> tuple[str, ...]:
        """Return uncovered block identities in authoritative order."""
        return tuple(
            review.block_id
            for review in self.block_reviews
            if review.status is LayoutBlockReviewStatus.UNCOVERED
        )

    @property
    def invalid_geometry_block_ids(self) -> tuple[str, ...]:
        """Return unmappable block identities in authoritative order."""
        return tuple(
            review.block_id
            for review in self.block_reviews
            if review.status is LayoutBlockReviewStatus.INVALID_GEOMETRY
        )

    @property
    def configuration_id(self) -> str:
        """Return request-bound configuration identity."""
        return self.request.configuration.configuration_id

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout review case contract")
        self.validate(
            request=self.request,
            block_reviews=self.block_reviews,
            page_coverage_ratio=self.page_coverage_ratio,
            reasons=self.reasons,
        )
        LayoutValueValidation.require_text(
            "actionizer_name", self.actionizer_name
        )
        LayoutValueValidation.require_text(
            "actionizer_version", self.actionizer_version
        )
        if self.requires_review is not bool(self.reasons):
            raise ValueError("requires_review must match reasons")
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.request.request_id,
            tuple(review.block_review_id for review in self.block_reviews),
            self.page_coverage_ratio,
            self.reasons,
            self.actionizer_name,
            self.actionizer_version,
            self.request.configuration.configuration_id,
        )
        if self.case_id != expected:
            raise ValueError("layout review case ID is inconsistent")

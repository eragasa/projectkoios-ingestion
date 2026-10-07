"""Normalized review evidence for one authoritative native text block."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.review.kind import LayoutBlockReviewStatus
from projectkoios.ingestion.layout.review.limits.definition import (
    MAX_LAYOUT_REVIEW_OVERLAPS,
)
from projectkoios.ingestion.layout.review.limits.error import (
    LayoutReviewLimitError,
)
from projectkoios.ingestion.layout.review.overlap import (
    LayoutBlockRegionOverlap,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class LayoutBlockReviewEvidence(AbstractImmutableDataObject):
    """Retain exact mapped coverage evidence for one native text block."""

    CONTRACT_NAME: ClassVar[str] = "layout-block-review-evidence"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    block_review_id: str
    render_id: str
    mapping_id: str
    block_id: str
    block_bounding_box_pixels: tuple[float, float, float, float] | None
    status: LayoutBlockReviewStatus
    overlaps: tuple[LayoutBlockRegionOverlap, ...]
    significant_proposal_ids: tuple[str, ...]
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        render_id: str,
        mapping_id: str,
        block_id: str,
        block_bounding_box_pixels: (
            tuple[float, float, float, float] | None
        ),
        status: LayoutBlockReviewStatus,
        overlaps: tuple[LayoutBlockRegionOverlap, ...],
        significant_proposal_ids: tuple[str, ...],
    ) -> LayoutBlockReviewEvidence:
        """Create one normalized per-block evidence record."""
        values = cls.validated_values(
            render_id=render_id,
            mapping_id=mapping_id,
            block_id=block_id,
            block_bounding_box_pixels=block_bounding_box_pixels,
            status=status,
            overlaps=overlaps,
            significant_proposal_ids=significant_proposal_ids,
        )
        block_review_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            *values,
        )
        return cls(
            block_review_id=block_review_id,
            render_id=values[0],
            mapping_id=values[1],
            block_id=values[2],
            block_bounding_box_pixels=values[3],
            status=values[4],
            overlaps=values[5],
            significant_proposal_ids=values[6],
        )

    @classmethod
    def validated_values(
        cls,
        *,
        render_id: object,
        mapping_id: object,
        block_id: object,
        block_bounding_box_pixels: object,
        status: object,
        overlaps: object,
        significant_proposal_ids: object,
    ) -> tuple[
        str,
        str,
        str,
        tuple[float, float, float, float] | None,
        LayoutBlockReviewStatus,
        tuple[LayoutBlockRegionOverlap, ...],
        tuple[str, ...],
    ]:
        """Validate references and coverage status without redundant state."""
        render = LayoutValueValidation.require_text("render_id", render_id)
        mapping = LayoutValueValidation.require_text("mapping_id", mapping_id)
        block = LayoutValueValidation.require_text("block_id", block_id)
        box = (
            None
            if block_bounding_box_pixels is None
            else LayoutValueValidation.require_box(
                "block_bounding_box_pixels", block_bounding_box_pixels
            )
        )
        if not isinstance(status, LayoutBlockReviewStatus):
            raise TypeError("status must be LayoutBlockReviewStatus")
        if not isinstance(overlaps, tuple) or any(
            type(overlap) is not LayoutBlockRegionOverlap
            for overlap in overlaps
        ):
            raise TypeError("overlaps must contain LayoutBlockRegionOverlap")
        if len(overlaps) > MAX_LAYOUT_REVIEW_OVERLAPS:
            raise LayoutReviewLimitError(
                "block overlaps exceed implementation maximum"
            )
        overlap_ids = tuple(overlap.overlap_id for overlap in overlaps)
        if len(set(overlap_ids)) != len(overlap_ids):
            raise ValueError("overlap IDs must be unique per block")
        proposal_ids = tuple(overlap.proposal_id for overlap in overlaps)
        if len(set(proposal_ids)) != len(proposal_ids):
            raise ValueError("a block may overlap each proposal at most once")
        if any(
            overlap.render_id != render
            or overlap.mapping_id != mapping
            or overlap.block_id != block
            or overlap.block_bounding_box_pixels != box
            for overlap in overlaps
        ):
            raise ValueError("overlap identity differs from block review")
        if not isinstance(significant_proposal_ids, tuple) or any(
            not isinstance(proposal_id, str) or not proposal_id
            for proposal_id in significant_proposal_ids
        ):
            raise TypeError(
                "significant_proposal_ids must contain non-empty strings"
            )
        significant = tuple(
            LayoutValueValidation.require_text(
                "significant_proposal_id", proposal_id
            )
            for proposal_id in significant_proposal_ids
        )
        if len(set(significant)) != len(significant):
            raise ValueError("significant proposal IDs must be unique")
        if not set(significant) <= set(proposal_ids):
            raise ValueError("significant proposals must identify overlaps")
        if status is LayoutBlockReviewStatus.INVALID_GEOMETRY:
            if box is not None or overlaps or significant:
                raise ValueError(
                    "invalid geometry cannot carry mapped overlap evidence"
                )
        elif status is LayoutBlockReviewStatus.COVERED:
            if box is None or not significant:
                raise ValueError("covered blocks require significant overlap")
        elif box is None or significant:
            raise ValueError(
                "uncovered blocks require mapped geometry and no significance"
            )
        return (
            render,
            mapping,
            block,
            box,
            status,
            overlaps,
            significant,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout block review contract")
        values = self.validated_values(
            render_id=self.render_id,
            mapping_id=self.mapping_id,
            block_id=self.block_id,
            block_bounding_box_pixels=self.block_bounding_box_pixels,
            status=self.status,
            overlaps=self.overlaps,
            significant_proposal_ids=self.significant_proposal_ids,
        )
        object.__setattr__(self, "block_bounding_box_pixels", values[3])
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            *values,
        )
        if self.block_review_id != expected:
            raise ValueError("layout block review ID is inconsistent")

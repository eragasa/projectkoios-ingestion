"""Deterministic native-block and proposed-region overlap evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.proposal.region import LayoutRegionProposal
from projectkoios.ingestion.layout.render.evidence import (
    LayoutPageRenderEvidence,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class LayoutBlockRegionOverlap(AbstractImmutableDataObject):
    """Measure one positive intersection in exact rendered pixel coordinates."""

    CONTRACT_NAME: ClassVar[str] = "layout-block-region-overlap"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    overlap_id: str
    render_id: str
    mapping_id: str
    block_id: str
    proposal_id: str
    block_bounding_box_pixels: tuple[float, float, float, float]
    intersection_box_pixels: tuple[float, float, float, float]
    intersection_over_block_area: float
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def measure(
        cls,
        *,
        block_id: str,
        block_bounding_box_pixels: tuple[float, float, float, float],
        proposal: LayoutRegionProposal,
        render: LayoutPageRenderEvidence,
    ) -> LayoutBlockRegionOverlap | None:
        """Return positive overlap evidence or ``None`` when disjoint."""
        block_identity = LayoutValueValidation.require_text(
            "block_id", block_id
        )
        block_box = LayoutValueValidation.require_box(
            "block_bounding_box_pixels", block_bounding_box_pixels
        )
        if (
            block_box[0] < 0.0
            or block_box[1] < 0.0
            or block_box[2] > render.image_width
            or block_box[3] > render.image_height
        ):
            raise ValueError("mapped block bounding box exceeds render bounds")
        proposed_box = proposal.bounding_box_pixels
        intersection = (
            max(block_box[0], proposed_box[0]),
            max(block_box[1], proposed_box[1]),
            min(block_box[2], proposed_box[2]),
            min(block_box[3], proposed_box[3]),
        )
        if (
            intersection[2] <= intersection[0]
            or intersection[3] <= intersection[1]
        ):
            return None
        intersection_box = LayoutValueValidation.require_box(
            "intersection_box_pixels", intersection
        )
        intersection_area = (
            intersection_box[2] - intersection_box[0]
        ) * (intersection_box[3] - intersection_box[1])
        block_area = (block_box[2] - block_box[0]) * (
            block_box[3] - block_box[1]
        )
        ratio = LayoutValueValidation.require_ratio(
            "intersection_over_block_area",
            round(intersection_area / block_area, 12),
        )
        overlap_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            render.render_id,
            render.mapping.mapping_id,
            block_identity,
            proposal.proposal_id,
            block_box,
            intersection_box,
            ratio,
        )
        return cls(
            overlap_id=overlap_id,
            render_id=render.render_id,
            mapping_id=render.mapping.mapping_id,
            block_id=block_identity,
            proposal_id=proposal.proposal_id,
            block_bounding_box_pixels=block_box,
            intersection_box_pixels=intersection_box,
            intersection_over_block_area=ratio,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout overlap contract")
        for name, value in (
            ("render_id", self.render_id),
            ("mapping_id", self.mapping_id),
            ("block_id", self.block_id),
            ("proposal_id", self.proposal_id),
        ):
            LayoutValueValidation.require_text(name, value)
        block_box = LayoutValueValidation.require_box(
            "block_bounding_box_pixels", self.block_bounding_box_pixels
        )
        intersection_box = LayoutValueValidation.require_box(
            "intersection_box_pixels", self.intersection_box_pixels
        )
        if (
            intersection_box[0] < block_box[0]
            or intersection_box[1] < block_box[1]
            or intersection_box[2] > block_box[2]
            or intersection_box[3] > block_box[3]
        ):
            raise ValueError("intersection exceeds mapped block bounds")
        object.__setattr__(self, "block_bounding_box_pixels", block_box)
        object.__setattr__(self, "intersection_box_pixels", intersection_box)
        ratio = LayoutValueValidation.require_ratio(
            "intersection_over_block_area", self.intersection_over_block_area
        )
        if ratio == 0.0:
            raise ValueError("overlap ratio must exceed zero")
        object.__setattr__(self, "intersection_over_block_area", ratio)
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.render_id,
            self.mapping_id,
            self.block_id,
            self.proposal_id,
            block_box,
            intersection_box,
            ratio,
        )
        if self.overlap_id != expected:
            raise ValueError("layout overlap ID is inconsistent")

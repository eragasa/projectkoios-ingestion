"""Deterministic native-block and proposed-region overlap evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.contracts import LayoutBlockReference
from projectkoios.ingestion.layout.proposal.region import LayoutRegionProposal
from projectkoios.ingestion.layout.render.evidence import (
    LayoutPageRenderEvidence,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class LayoutBlockRegionOverlap(AbstractImmutableDataObject):
    """Measure one positive intersection in rendered pixel coordinates."""

    CONTRACT_NAME: ClassVar[str] = "layout-block-region-overlap"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    overlap_id: str
    render_id: str
    block_id: str
    proposal_id: str
    intersection_box_pixels: tuple[float, float, float, float]
    intersection_over_block_area: float
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def measure(
        cls,
        *,
        block: LayoutBlockReference,
        proposal: LayoutRegionProposal,
        render: LayoutPageRenderEvidence,
        page_width: float,
        page_height: float,
    ) -> LayoutBlockRegionOverlap | None:
        """Return positive overlap evidence or ``None`` when disjoint."""
        source_box = block.bounding_box
        if source_box is None:
            return None
        x_scale = render.image_width / page_width
        y_scale = render.image_height / page_height
        block_box = (
            source_box[0] * x_scale,
            source_box[1] * y_scale,
            source_box[2] * x_scale,
            source_box[3] * y_scale,
        )
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
        intersection_area = (intersection[2] - intersection[0]) * (
            intersection[3] - intersection[1]
        )
        block_area = (block_box[2] - block_box[0]) * (
            block_box[3] - block_box[1]
        )
        ratio = round(intersection_area / block_area, 12)
        overlap_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            render.render_id,
            block.block_id,
            proposal.proposal_id,
            intersection,
            ratio,
        )
        return cls(
            overlap_id=overlap_id,
            render_id=render.render_id,
            block_id=block.block_id,
            proposal_id=proposal.proposal_id,
            intersection_box_pixels=intersection,
            intersection_over_block_area=ratio,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout overlap contract")
        LayoutValueValidation.require_text("render_id", self.render_id)
        LayoutValueValidation.require_text("block_id", self.block_id)
        LayoutValueValidation.require_text("proposal_id", self.proposal_id)
        box = LayoutValueValidation.require_box(
            "intersection_box_pixels", self.intersection_box_pixels
        )
        object.__setattr__(self, "intersection_box_pixels", box)
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
            self.block_id,
            self.proposal_id,
            box,
            ratio,
        )
        if self.overlap_id != expected:
            raise ValueError("layout overlap ID is inconsistent")

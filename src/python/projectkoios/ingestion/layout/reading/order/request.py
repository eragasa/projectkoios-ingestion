"""Immutable deterministic reading-order resolution requests."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.render.evidence import (
    LayoutPageRenderEvidence,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

from .block import LayoutReadingOrderExpectedBlockInventory
from .candidate import LayoutReadingOrderCandidateEvidence
from .configuration import LayoutReadingOrderConfiguration
from .kind import LayoutReadingDirection
from .region import LayoutReadingOrderRegionInventory


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderRequest(
    ConfigurableDataObjectActionRequest[LayoutReadingOrderConfiguration]
):
    """Bind exact evidence, candidate, geometry, and required block coverage."""

    render: LayoutPageRenderEvidence
    upstream_evidence_id: str
    direction: LayoutReadingDirection
    expected_blocks: LayoutReadingOrderExpectedBlockInventory
    regions: LayoutReadingOrderRegionInventory
    candidate_evidence: LayoutReadingOrderCandidateEvidence
    configuration: LayoutReadingOrderConfiguration
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.render) is not LayoutPageRenderEvidence:
            raise TypeError("render must be LayoutPageRenderEvidence")
        upstream = LayoutValueValidation.require_text(
            "upstream_evidence_id", self.upstream_evidence_id
        )
        if not isinstance(self.direction, LayoutReadingDirection):
            raise TypeError("direction must be LayoutReadingDirection")
        if (
            type(self.expected_blocks)
            is not LayoutReadingOrderExpectedBlockInventory
        ):
            raise TypeError(
                "expected_blocks must be an expected block inventory"
            )
        if type(self.regions) is not LayoutReadingOrderRegionInventory:
            raise TypeError("regions must be LayoutReadingOrderRegionInventory")
        if (
            type(self.candidate_evidence)
            is not LayoutReadingOrderCandidateEvidence
        ):
            raise TypeError(
                "candidate_evidence must be LayoutReadingOrderCandidateEvidence"
            )
        if type(self.configuration) is not LayoutReadingOrderConfiguration:
            raise TypeError(
                "configuration must be LayoutReadingOrderConfiguration"
            )
        if len(self.regions) > self.configuration.maximum_regions:
            raise ValueError("regions exceed configured maximum")
        assigned_block_count = sum(
            len(region.blocks) for region in self.regions
        )
        if (
            len(self.expected_blocks) > self.configuration.maximum_native_blocks
            or assigned_block_count > self.configuration.maximum_native_blocks
        ):
            raise ValueError("native blocks exceed configured maximum")
        for region in self.regions:
            require_layout_reading_order_box_in_page(
                box=region.bounding_box_pixels,
                width=self.render.image_width,
                height=self.render.image_height,
            )
            for block in region.blocks:
                require_layout_reading_order_box_in_page(
                    box=block.bounding_box_pixels,
                    width=self.render.image_width,
                    height=self.render.image_height,
                )
        evidence = self.candidate_evidence
        if (
            evidence.render_id != self.render.render_id
            or evidence.upstream_evidence_id != upstream
            or evidence.direction is not self.direction
        ):
            raise ValueError(
                "candidate evidence differs from resolver page lineage"
            )
        elements = tuple(evidence.elements)
        regions = tuple(self.regions)
        if len(elements) != len(regions) or any(
            element.region_id != region.region_id
            or element.kind is not region.kind
            or element.bounding_box_pixels != region.bounding_box_pixels
            for element, region in zip(elements, regions, strict=False)
        ):
            raise ValueError(
                "candidate evidence differs from resolver region evidence"
            )
        object.__setattr__(self, "upstream_evidence_id", upstream)
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                "layout-reading-order-request",
                self.render.render_id,
                upstream,
                self.direction,
                self.expected_blocks.inventory_id,
                self.regions.inventory_id,
                self.candidate_evidence.evidence_id,
                self.configuration.configuration_id,
            ),
        )


def require_layout_reading_order_box_in_page(
    *,
    box: tuple[float, float, float, float],
    width: int,
    height: int,
) -> None:
    """Reject geometry outside the exact bound render dimensions."""
    x1, y1, x2, y2 = box
    if x1 < 0.0 or y1 < 0.0 or x2 > width or y2 > height:
        raise ValueError("reading-order geometry exceeds page bounds")

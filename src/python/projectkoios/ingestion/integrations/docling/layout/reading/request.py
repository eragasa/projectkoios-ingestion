"""Immutable Docling reading-order candidate requests."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.reading.order.candidate import (
    LayoutReadingOrderCandidateElementInventory,
)
from projectkoios.ingestion.layout.reading.order.kind import (
    LayoutReadingDirection,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

from .configuration import DoclingReadingOrderConfiguration
from .limits import MAX_DOCLING_READING_ORDER_PAGE_DIMENSION


@dataclass(frozen=True, slots=True)
class DoclingReadingOrderRequest(
    ConfigurableDataObjectActionRequest[DoclingReadingOrderConfiguration]
):
    """Bind exact render, upstream lineage, geometry, and source order."""

    render_id: str
    upstream_evidence_id: str
    page_width_pixels: int
    page_height_pixels: int
    direction: LayoutReadingDirection
    elements: LayoutReadingOrderCandidateElementInventory
    configuration: DoclingReadingOrderConfiguration
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        render = LayoutValueValidation.require_text("render_id", self.render_id)
        upstream = LayoutValueValidation.require_text(
            "upstream_evidence_id", self.upstream_evidence_id
        )
        width = LayoutValueValidation.require_positive_integer(
            "page_width_pixels",
            self.page_width_pixels,
            maximum=MAX_DOCLING_READING_ORDER_PAGE_DIMENSION,
        )
        height = LayoutValueValidation.require_positive_integer(
            "page_height_pixels",
            self.page_height_pixels,
            maximum=MAX_DOCLING_READING_ORDER_PAGE_DIMENSION,
        )
        if not isinstance(self.direction, LayoutReadingDirection):
            raise TypeError("direction must be LayoutReadingDirection")
        if (
            type(self.elements)
            is not LayoutReadingOrderCandidateElementInventory
        ):
            raise TypeError(
                "elements must be LayoutReadingOrderCandidateElementInventory"
            )
        if type(self.configuration) is not DoclingReadingOrderConfiguration:
            raise TypeError(
                "configuration must be DoclingReadingOrderConfiguration"
            )
        if len(self.elements) > self.configuration.maximum_elements:
            raise ValueError("elements exceed configured maximum")
        for element in self.elements:
            x1, y1, x2, y2 = element.bounding_box_pixels
            if x1 < 0.0 or y1 < 0.0 or x2 > width or y2 > height:
                raise ValueError("reading-order element exceeds page bounds")
        object.__setattr__(self, "render_id", render)
        object.__setattr__(self, "upstream_evidence_id", upstream)
        object.__setattr__(self, "page_width_pixels", width)
        object.__setattr__(self, "page_height_pixels", height)
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                "docling-reading-order-request",
                render,
                upstream,
                width,
                height,
                self.direction,
                self.elements.inventory_id,
                self.configuration.configuration_id,
            ),
        )

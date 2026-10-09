"""COCO reading-order projection results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.reading.order import (
    CocoLayoutImageReadingOrder,
)

from .derivation import derive_coco_layout_image_reading_order
from .request import CocoLayoutReadingOrderProjectionRequest


@dataclass(frozen=True, slots=True)
class CocoLayoutReadingOrderProjectionResult(AbstractDataObjectActionResult):
    """Bind one strict per-image COCO reading-order record to its request."""

    ACTIONIZER_NAME: ClassVar[str] = "coco-layout-reading-order-projector"
    ACTIONIZER_VERSION: ClassVar[str] = "1"

    request: CocoLayoutReadingOrderProjectionRequest
    reading_order: CocoLayoutImageReadingOrder
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not CocoLayoutReadingOrderProjectionRequest:
            raise TypeError(
                "request must be CocoLayoutReadingOrderProjectionRequest"
            )
        if type(self.reading_order) is not CocoLayoutImageReadingOrder:
            raise TypeError("reading_order must be CocoLayoutImageReadingOrder")
        expected = derive_coco_layout_image_reading_order(request=self.request)
        if self.reading_order != expected:
            raise ValueError("projected reading order differs from derivation")
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                "coco-layout-reading-order-projection-result",
                self.request.request_id,
                self.reading_order.reading_order_id,
                self.ACTIONIZER_NAME,
                self.ACTIONIZER_VERSION,
            ),
        )

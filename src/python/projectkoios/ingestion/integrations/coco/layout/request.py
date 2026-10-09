"""Immutable request to adapt exact COCO layout detections."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.configuration import (
    CocoLayoutProposalConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.detection import (
    CocoLayoutDetectionInventory,
)
from projectkoios.ingestion.integrations.coco.layout.image import (
    CocoLayoutImage,
)
from projectkoios.ingestion.layout.render.evidence import (
    LayoutPageRenderEvidence,
)


@dataclass(frozen=True, slots=True)
class CocoLayoutProposalRequest(
    ConfigurableDataObjectActionRequest[CocoLayoutProposalConfiguration]
):
    """Bind an exact render, COCO image, detections, and pinned profile."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-proposal-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    render: LayoutPageRenderEvidence
    image: CocoLayoutImage
    detections: CocoLayoutDetectionInventory
    configuration: CocoLayoutProposalConfiguration
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.render) is not LayoutPageRenderEvidence:
            raise TypeError("render must be LayoutPageRenderEvidence")
        if type(self.image) is not CocoLayoutImage:
            raise TypeError("image must be CocoLayoutImage")
        if type(self.detections) is not CocoLayoutDetectionInventory:
            raise TypeError("detections must be CocoLayoutDetectionInventory")
        if type(self.configuration) is not CocoLayoutProposalConfiguration:
            raise TypeError(
                "configuration must be CocoLayoutProposalConfiguration"
            )
        if (
            self.image.render_id != self.render.render_id
            or self.image.width != self.render.image_width
            or self.image.height != self.render.image_height
            or self.image.image_media_type != self.render.image_media_type
            or self.image.image_sha256 != self.render.image_sha256
        ):
            raise ValueError("COCO image differs from the exact page render")
        if len(self.detections) > self.configuration.max_detections:
            raise ValueError("COCO detections exceed the configured maximum")
        for detection in self.detections:
            if detection.image_id != self.image.image_id:
                raise ValueError("COCO detection identifies another image")
            self.configuration.profile.categories.require(detection.category_id)
            x1, y1, x2, y2 = detection.bounding_box_pixels
            if (
                x1 < 0.0
                or y1 < 0.0
                or x2 > self.image.width
                or y2 > self.image.height
            ):
                raise ValueError("COCO detection exceeds image bounds")
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.render.render_id,
                self.image.image_identity,
                self.detections.inventory_id,
                self.configuration.configuration_id,
            ),
        )

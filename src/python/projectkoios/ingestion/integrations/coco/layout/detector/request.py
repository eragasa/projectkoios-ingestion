"""Immutable requests to normalize frozen local detector observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.image import (
    CocoLayoutImage,
)
from projectkoios.ingestion.layout.render.evidence import (
    LayoutPageRenderEvidence,
)

from .configuration import CocoLayoutDetectorConfiguration
from .observation import CocoLayoutDetectorObservationInventory


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorRequest(
    ConfigurableDataObjectActionRequest[CocoLayoutDetectorConfiguration]
):
    """Bind exact render evidence and raw local detector observations."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-detector-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    render: LayoutPageRenderEvidence
    image: CocoLayoutImage
    observations: CocoLayoutDetectorObservationInventory
    configuration: CocoLayoutDetectorConfiguration
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.render) is not LayoutPageRenderEvidence:
            raise TypeError("render must be LayoutPageRenderEvidence")
        if type(self.image) is not CocoLayoutImage:
            raise TypeError("image must be CocoLayoutImage")
        # This action normalizes one rendered page. Multi-page bundle IDs are
        # assigned only when independently normalized page records are combined.
        if self.image.image_id != 1:
            raise ValueError("single-page detector image ID must be one")
        if (
            type(self.observations)
            is not CocoLayoutDetectorObservationInventory
        ):
            raise TypeError(
                "observations must be a detector observation inventory"
            )
        if type(self.configuration) is not CocoLayoutDetectorConfiguration:
            raise TypeError(
                "configuration must be CocoLayoutDetectorConfiguration"
            )
        if (
            self.image.render_id != self.render.render_id
            or self.image.width != self.render.image_width
            or self.image.height != self.render.image_height
            or self.image.image_media_type != self.render.image_media_type
            or self.image.image_sha256 != self.render.image_sha256
        ):
            raise ValueError(
                "detector image differs from the exact page render"
            )
        if len(self.observations) > self.configuration.maximum_observations:
            raise ValueError(
                "detector observations exceed the configured maximum"
            )
        for observation in self.observations:
            if observation.render_id != self.render.render_id:
                raise ValueError(
                    "detector observation identifies another render"
                )
            self.configuration.label_mappings.require(
                observation.model_label_id
            )
            x1, y1, x2, y2 = observation.bounding_box_xyxy_pixels
            if (
                x1 < 0.0
                or y1 < 0.0
                or x2 > self.image.width
                or y2 > self.image.height
            ):
                raise ValueError("detector observation exceeds image bounds")
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.render.render_id,
                self.image.image_identity,
                self.observations.inventory_id,
                self.configuration.configuration_id,
            ),
        )

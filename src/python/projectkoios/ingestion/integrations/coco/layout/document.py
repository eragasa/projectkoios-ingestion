"""Typed COCO layout annotation document."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.detection import (
    CocoLayoutDetectionInventory,
)
from projectkoios.ingestion.integrations.coco.layout.image import (
    CocoLayoutImageInventory,
)
from projectkoios.ingestion.integrations.coco.layout.profile import (
    CocoLayoutProfile,
)


@dataclass(frozen=True, slots=True)
class CocoLayoutAnnotationDocument(AbstractImmutableDataObject):
    """Own the strict COCO-compatible region document for one bundle."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-annotation-document"
    CONTRACT_VERSION: ClassVar[str] = "0.1"

    profile: CocoLayoutProfile
    images: CocoLayoutImageInventory
    detections: CocoLayoutDetectionInventory
    document_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.profile) is not CocoLayoutProfile:
            raise TypeError("profile must be CocoLayoutProfile")
        if self.profile != CocoLayoutProfile.koios_doclaynet_v0_1():
            raise ValueError(
                "annotation document requires Koios COCO Layout Profile v0.1"
            )
        if type(self.images) is not CocoLayoutImageInventory:
            raise TypeError("images must be CocoLayoutImageInventory")
        if type(self.detections) is not CocoLayoutDetectionInventory:
            raise TypeError("detections must be CocoLayoutDetectionInventory")
        images = tuple(self.images)
        image_ids = tuple(image.image_id for image in images)
        if image_ids != tuple(range(1, len(images) + 1)):
            raise ValueError("COCO image IDs must be contiguous from one")
        render_ids = tuple(image.render_id for image in images)
        if render_ids != tuple(sorted(render_ids)):
            raise ValueError("COCO image IDs must follow render identity order")
        detections = tuple(self.detections)
        annotation_ids = tuple(
            detection.annotation_id for detection in detections
        )
        if annotation_ids != tuple(range(1, len(detections) + 1)):
            raise ValueError("COCO annotation IDs must be contiguous from one")
        semantic_keys = tuple(
            (
                detection.image_id,
                detection.category_id,
                detection.bbox_xywh_pixels,
                detection.confidence,
            )
            for detection in detections
        )
        if semantic_keys != tuple(sorted(semantic_keys)):
            raise ValueError(
                "COCO annotation IDs must follow canonical semantic order"
            )
        if len(semantic_keys) != len(set(semantic_keys)):
            raise ValueError("COCO annotations must be semantically unique")
        for detection in detections:
            image = self.images.require(detection.image_id)
            self.profile.categories.require(detection.category_id)
            _, _, x2, y2 = detection.bounding_box_pixels
            if x2 > image.width or y2 > image.height:
                raise ValueError("COCO annotation exceeds image bounds")
        object.__setattr__(
            self,
            "document_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.profile.profile_id,
                self.images.inventory_id,
                self.detections.inventory_id,
            ),
        )

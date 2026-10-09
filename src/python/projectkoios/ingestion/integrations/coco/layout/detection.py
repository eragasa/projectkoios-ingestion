"""Frozen box detections using COCO pixel geometry."""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_DETECTIONS,
)
from projectkoios.ingestion.integrations.coco.layout.limits.error import (
    CocoLayoutLimitError,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class CocoLayoutDetection(AbstractImmutableDataObject):
    """Retain one exact COCO annotation ID, category, box, and score."""

    annotation_id: int
    image_id: int
    category_id: int
    bbox_xywh_pixels: tuple[float, float, float, float]
    confidence: float
    detection_id: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("annotation_id", "image_id", "category_id"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer")
        if (
            not isinstance(self.bbox_xywh_pixels, tuple)
            or len(self.bbox_xywh_pixels) != 4
            or any(
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(float(value))
                for value in self.bbox_xywh_pixels
            )
        ):
            raise ValueError("bbox_xywh_pixels must contain four finite values")
        x, y, width, height = (float(value) for value in self.bbox_xywh_pixels)
        if x < 0.0 or y < 0.0 or width <= 0.0 or height <= 0.0:
            raise ValueError(
                "COCO box origin must be non-negative and extent positive"
            )
        box = (x, y, width, height)
        score = LayoutValueValidation.require_ratio(
            "confidence", self.confidence
        )
        object.__setattr__(self, "bbox_xywh_pixels", box)
        object.__setattr__(self, "confidence", score)
        object.__setattr__(
            self,
            "detection_id",
            stable_id(
                "coco-layout-detection",
                self.annotation_id,
                self.image_id,
                self.category_id,
                box,
                score,
            ),
        )

    @property
    def bounding_box_pixels(self) -> tuple[float, float, float, float]:
        """Return lossless internal ``x1, y1, x2, y2`` pixel geometry."""
        x, y, width, height = self.bbox_xywh_pixels
        return (x, y, x + width, y + height)


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutDetectionInventory:
    """Own one ordered, unique, bounded COCO detection collection."""

    _detections: tuple[CocoLayoutDetection, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *detections: CocoLayoutDetection) -> None:
        values = tuple(detections)
        if len(values) > MAX_COCO_LAYOUT_DETECTIONS:
            raise CocoLayoutLimitError(
                "COCO detections exceed their implementation limit"
            )
        if any(type(value) is not CocoLayoutDetection for value in values):
            raise TypeError(
                "COCO detection inventory requires exact detections"
            )
        annotation_ids = tuple(value.annotation_id for value in values)
        if annotation_ids != tuple(sorted(annotation_ids)):
            raise ValueError("COCO detections must be sorted by annotation_id")
        if len(annotation_ids) != len(set(annotation_ids)):
            raise ValueError("COCO annotation IDs must be unique")
        detection_ids = tuple(value.detection_id for value in values)
        if len(detection_ids) != len(set(detection_ids)):
            raise ValueError("COCO detection identities must be unique")
        object.__setattr__(self, "_detections", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id("coco-layout-detection-inventory", detection_ids),
        )

    def __iter__(self) -> Iterator[CocoLayoutDetection]:
        return iter(self._detections)

    def __len__(self) -> int:
        return len(self._detections)

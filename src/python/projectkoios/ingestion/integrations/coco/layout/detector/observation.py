"""Frozen framework-neutral local detector observations."""

from __future__ import annotations

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
class CocoLayoutDetectorObservation(AbstractImmutableDataObject):
    """Retain one raw model-label, XYXY box, and confidence observation."""

    render_id: str
    model_label_id: int
    bounding_box_xyxy_pixels: tuple[float, float, float, float]
    confidence: float
    observation_id: str = field(init=False)

    def __post_init__(self) -> None:
        render_id = LayoutValueValidation.require_text(
            "render_id", self.render_id
        )
        label_id = LayoutValueValidation.require_nonnegative_integer(
            "model_label_id", self.model_label_id
        )
        box = LayoutValueValidation.require_box(
            "bounding_box_xyxy_pixels", self.bounding_box_xyxy_pixels
        )
        score = LayoutValueValidation.require_ratio(
            "confidence", self.confidence
        )
        object.__setattr__(self, "render_id", render_id)
        object.__setattr__(self, "model_label_id", label_id)
        object.__setattr__(self, "bounding_box_xyxy_pixels", box)
        object.__setattr__(self, "confidence", score)
        object.__setattr__(
            self,
            "observation_id",
            stable_id(
                "coco-layout-detector-observation",
                render_id,
                label_id,
                box,
                score,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutDetectorObservationInventory:
    """Retain bounded producer-declared local detector output order."""

    _observations: tuple[CocoLayoutDetectorObservation, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *observations: CocoLayoutDetectorObservation) -> None:
        values = tuple(observations)
        if len(values) > MAX_COCO_LAYOUT_DETECTIONS:
            raise CocoLayoutLimitError(
                "detector observations exceed their implementation limit"
            )
        if any(
            type(value) is not CocoLayoutDetectorObservation for value in values
        ):
            raise TypeError(
                "detector observation inventory requires exact observations"
            )
        identities = tuple(value.observation_id for value in values)
        if len(identities) != len(set(identities)):
            raise ValueError("detector observations must be unique")
        object.__setattr__(self, "_observations", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id("coco-layout-detector-observation-inventory", identities),
        )

    def __iter__(self) -> Iterator[CocoLayoutDetectorObservation]:
        return iter(self._observations)

    def __len__(self) -> int:
        return len(self._observations)

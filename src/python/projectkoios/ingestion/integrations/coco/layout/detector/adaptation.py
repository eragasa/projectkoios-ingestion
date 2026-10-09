"""Exact raw-observation to COCO-detection adaptation evidence."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.detection import (
    CocoLayoutDetection,
)
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_DETECTIONS,
)
from projectkoios.ingestion.integrations.coco.layout.limits.error import (
    CocoLayoutLimitError,
)

from .label import (
    CocoLayoutDetectorLabelDisposition,
    CocoLayoutDetectorLabelMapping,
)
from .observation import CocoLayoutDetectorObservation


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorAdaptation(AbstractImmutableDataObject):
    """Bind one accepted raw observation to one exact COCO detection."""

    observation: CocoLayoutDetectorObservation
    mapping: CocoLayoutDetectorLabelMapping
    detection: CocoLayoutDetection
    adaptation_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.observation) is not CocoLayoutDetectorObservation:
            raise TypeError("observation must be CocoLayoutDetectorObservation")
        if type(self.mapping) is not CocoLayoutDetectorLabelMapping:
            raise TypeError("mapping must be CocoLayoutDetectorLabelMapping")
        if type(self.detection) is not CocoLayoutDetection:
            raise TypeError("detection must be CocoLayoutDetection")
        if (
            self.mapping.disposition
            is not CocoLayoutDetectorLabelDisposition.ACCEPTED
            or self.mapping.model_label_id != self.observation.model_label_id
            or self.mapping.category_id != self.detection.category_id
            or self.observation.confidence != self.detection.confidence
            or self.observation.bounding_box_xyxy_pixels
            != self.detection.bounding_box_pixels
        ):
            raise ValueError(
                "detector adaptation differs from observation or mapping"
            )
        object.__setattr__(
            self,
            "adaptation_id",
            stable_id(
                "coco-layout-detector-adaptation",
                self.observation.observation_id,
                self.mapping.mapping_id,
                self.detection.detection_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class CocoLayoutDetectorAdaptationInventory:
    """Own canonical detection-ordered local detector adaptations."""

    _adaptations: tuple[CocoLayoutDetectorAdaptation, ...] = field(repr=True)
    inventory_id: str = field(init=False)

    def __init__(self, *adaptations: CocoLayoutDetectorAdaptation) -> None:
        values = tuple(adaptations)
        if len(values) > MAX_COCO_LAYOUT_DETECTIONS:
            raise CocoLayoutLimitError(
                "detector adaptations exceed their implementation limit"
            )
        if any(
            type(value) is not CocoLayoutDetectorAdaptation for value in values
        ):
            raise TypeError(
                "detector adaptation inventory requires exact adaptations"
            )
        annotation_ids = tuple(
            value.detection.annotation_id for value in values
        )
        if annotation_ids != tuple(range(1, len(values) + 1)):
            raise ValueError(
                "detector adaptations require contiguous annotation IDs"
            )
        observation_ids = tuple(
            value.observation.observation_id for value in values
        )
        if len(observation_ids) != len(set(observation_ids)):
            raise ValueError("detector adaptations must use observations once")
        object.__setattr__(self, "_adaptations", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "coco-layout-detector-adaptation-inventory",
                tuple(value.adaptation_id for value in values),
            ),
        )

    def __iter__(self) -> Iterator[CocoLayoutDetectorAdaptation]:
        return iter(self._adaptations)

    def __len__(self) -> int:
        return len(self._adaptations)

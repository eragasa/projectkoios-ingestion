"""Configuration for generic per-category COCO region admission."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_DETECTIONS,
)
from projectkoios.ingestion.integrations.coco.layout.profile import (
    CocoLayoutProfile,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class CocoLayoutRegionAdmissionConfiguration(AbstractActionConfiguration):
    """Pin one default policy applied independently to every category."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-region-admission-configuration"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    profile: CocoLayoutProfile
    minimum_confidence: float = 0.5
    duplicate_iou_threshold: float = 0.8
    maximum_regions_per_category: int = MAX_COCO_LAYOUT_DETECTIONS
    configuration_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.profile) is not CocoLayoutProfile:
            raise TypeError("profile must be CocoLayoutProfile")
        minimum = LayoutValueValidation.require_ratio(
            "minimum_confidence", self.minimum_confidence
        )
        duplicate = LayoutValueValidation.require_ratio(
            "duplicate_iou_threshold", self.duplicate_iou_threshold
        )
        if duplicate <= 0.0:
            raise ValueError("duplicate_iou_threshold must be positive")
        maximum = LayoutValueValidation.require_positive_integer(
            "maximum_regions_per_category",
            self.maximum_regions_per_category,
            maximum=MAX_COCO_LAYOUT_DETECTIONS,
        )
        object.__setattr__(self, "minimum_confidence", minimum)
        object.__setattr__(self, "duplicate_iou_threshold", duplicate)
        object.__setattr__(
            self,
            "configuration_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.profile.profile_id,
                minimum,
                duplicate,
                maximum,
            ),
        )

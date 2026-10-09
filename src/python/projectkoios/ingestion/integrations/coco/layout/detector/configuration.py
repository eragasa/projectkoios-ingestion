"""Framework-neutral local detector adaptation configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.detector.label import (
    CocoLayoutDetectorLabelDisposition,
    CocoLayoutDetectorLabelMappingInventory,
)
from projectkoios.ingestion.integrations.coco.layout.detector.resource import (
    CocoLayoutDetectorResource,
)
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_DETECTIONS,
)
from projectkoios.ingestion.integrations.coco.layout.profile import (
    CocoLayoutProfile,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorConfiguration(AbstractActionConfiguration):
    """Pin detector resource, runtime, labels, threshold, and bounds."""

    profile: CocoLayoutProfile
    resource: CocoLayoutDetectorResource
    runtime_name: str
    runtime_version: str
    label_mappings: CocoLayoutDetectorLabelMappingInventory
    minimum_confidence: float
    maximum_observations: int
    configuration_id: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.profile) is not CocoLayoutProfile:
            raise TypeError("profile must be CocoLayoutProfile")
        if type(self.resource) is not CocoLayoutDetectorResource:
            raise TypeError("resource must be CocoLayoutDetectorResource")
        runtime_name = LayoutValueValidation.require_text(
            "runtime_name", self.runtime_name
        )
        runtime_version = LayoutValueValidation.require_text(
            "runtime_version", self.runtime_version
        )
        if (
            type(self.label_mappings)
            is not CocoLayoutDetectorLabelMappingInventory
        ):
            raise TypeError(
                "label_mappings must be a detector label mapping inventory"
            )
        category_ids = {
            category.category_id for category in self.profile.categories
        }
        accepted = {
            mapping.category_id
            for mapping in self.label_mappings
            if mapping.disposition
            is CocoLayoutDetectorLabelDisposition.ACCEPTED
        }
        if not accepted or not accepted <= category_ids:
            raise ValueError(
                "accepted detector labels must map to profile categories"
            )
        threshold = LayoutValueValidation.require_ratio(
            "minimum_confidence", self.minimum_confidence
        )
        maximum = LayoutValueValidation.require_positive_integer(
            "maximum_observations",
            self.maximum_observations,
            maximum=MAX_COCO_LAYOUT_DETECTIONS,
        )
        object.__setattr__(self, "runtime_name", runtime_name)
        object.__setattr__(self, "runtime_version", runtime_version)
        object.__setattr__(self, "minimum_confidence", threshold)
        object.__setattr__(
            self,
            "configuration_id",
            stable_id(
                "coco-layout-detector-configuration",
                self.profile.profile_id,
                self.resource.resource_id,
                runtime_name,
                runtime_version,
                self.label_mappings.inventory_id,
                threshold,
                maximum,
            ),
        )

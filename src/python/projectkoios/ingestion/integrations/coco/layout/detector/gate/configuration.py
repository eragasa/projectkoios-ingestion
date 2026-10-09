"""Deterministic local-detector admission-gate configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.limits.definition import (
    MAX_COCO_LAYOUT_DETECTIONS,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorGateConfiguration(AbstractActionConfiguration):
    """Bind explicit escalation policy and hard limitation bounds."""

    minimum_accepted_detections: int = 1
    maximum_limitations: int = MAX_COCO_LAYOUT_DETECTIONS
    unsupported_labels_require_escalation: bool = True
    configuration_id: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        minimum = LayoutValueValidation.require_positive_integer(
            "minimum_accepted_detections",
            self.minimum_accepted_detections,
            maximum=MAX_COCO_LAYOUT_DETECTIONS,
        )
        maximum = LayoutValueValidation.require_nonnegative_integer(
            "maximum_limitations",
            self.maximum_limitations,
            maximum=MAX_COCO_LAYOUT_DETECTIONS,
        )
        if type(self.unsupported_labels_require_escalation) is not bool:
            raise TypeError(
                "unsupported_labels_require_escalation must be bool"
            )
        object.__setattr__(
            self,
            "configuration_id",
            stable_id(
                "coco-layout-detector-gate-configuration",
                minimum,
                maximum,
                self.unsupported_labels_require_escalation,
            ),
        )

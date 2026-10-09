"""Configuration for admitted COCO formula projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

MAX_COCO_LAYOUT_EQUATION_CANDIDATES = 256


@dataclass(frozen=True, slots=True)
class CocoLayoutEquationProjectionConfiguration(AbstractActionConfiguration):
    """Pin formula confidence, deduplication, padding, and count bounds."""

    CONTRACT_NAME: ClassVar[str] = (
        "coco-layout-equation-projection-configuration"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    minimum_confidence: float = 0.8
    duplicate_iou_threshold: float = 0.8
    source_padding_points: float = 3.0
    maximum_candidates: int = MAX_COCO_LAYOUT_EQUATION_CANDIDATES
    configuration_id: str = field(init=False)

    def __post_init__(self) -> None:
        minimum = LayoutValueValidation.require_ratio(
            "minimum_confidence", self.minimum_confidence
        )
        duplicate = LayoutValueValidation.require_ratio(
            "duplicate_iou_threshold", self.duplicate_iou_threshold
        )
        if duplicate <= 0.0:
            raise ValueError("duplicate_iou_threshold must be positive")
        padding = LayoutValueValidation.require_number(
            "source_padding_points", self.source_padding_points
        )
        if padding < 0.0 or padding > 72.0:
            raise ValueError(
                "source_padding_points must be between zero and 72"
            )
        maximum = LayoutValueValidation.require_positive_integer(
            "maximum_candidates", self.maximum_candidates
        )
        if maximum > MAX_COCO_LAYOUT_EQUATION_CANDIDATES:
            raise ValueError(
                "maximum_candidates exceeds the implementation limit"
            )
        object.__setattr__(self, "minimum_confidence", minimum)
        object.__setattr__(self, "duplicate_iou_threshold", duplicate)
        object.__setattr__(self, "source_padding_points", padding)
        object.__setattr__(
            self,
            "configuration_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                minimum,
                duplicate,
                padding,
                maximum,
            ),
        )

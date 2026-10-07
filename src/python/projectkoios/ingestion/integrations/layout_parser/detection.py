"""Frozen raw LayoutParser detection records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

from .limits.definition import MAX_LAYOUT_PARSER_LABEL_CHARACTERS
from .limits.error import LayoutParserLimitError


@dataclass(frozen=True, slots=True)
class LayoutParserDetection(AbstractImmutableDataObject):
    """Retain one raw backend label, box, and score before domain mapping."""

    CONTRACT_NAME: ClassVar[str] = "layout-parser-detection"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    detection_id: str
    render_id: str
    label: str
    bounding_box_pixels: tuple[float, float, float, float]
    confidence: float
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        render_id: str,
        label: str,
        bounding_box_pixels: tuple[float, float, float, float],
        confidence: float,
    ) -> LayoutParserDetection:
        """Create one stable raw detection from isolated inference output."""
        render = LayoutValueValidation.require_text("render_id", render_id)
        model_label = LayoutValueValidation.require_text("label", label)
        if len(model_label) > MAX_LAYOUT_PARSER_LABEL_CHARACTERS:
            raise LayoutParserLimitError(
                "label exceeds implementation character limit"
            )
        box = LayoutValueValidation.require_box(
            "bounding_box_pixels", bounding_box_pixels
        )
        score = LayoutValueValidation.require_ratio("confidence", confidence)
        detection_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            render,
            model_label,
            box,
            score,
        )
        return cls(
            detection_id=detection_id,
            render_id=render,
            label=model_label,
            bounding_box_pixels=box,
            confidence=score,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported LayoutParser detection contract")
        LayoutValueValidation.require_text("render_id", self.render_id)
        model_label = LayoutValueValidation.require_text("label", self.label)
        if len(model_label) > MAX_LAYOUT_PARSER_LABEL_CHARACTERS:
            raise LayoutParserLimitError(
                "label exceeds implementation character limit"
            )
        box = LayoutValueValidation.require_box(
            "bounding_box_pixels", self.bounding_box_pixels
        )
        object.__setattr__(self, "bounding_box_pixels", box)
        score = LayoutValueValidation.require_ratio(
            "confidence", self.confidence
        )
        object.__setattr__(self, "confidence", score)
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.render_id,
            self.label,
            box,
            score,
        )
        if self.detection_id != expected:
            raise ValueError("LayoutParser detection ID is inconsistent")

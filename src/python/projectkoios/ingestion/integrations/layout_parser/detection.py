"""Frozen raw LayoutParser detection records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.models import Metadata


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
    evidence: Metadata
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        render_id: str,
        label: str,
        bounding_box_pixels: tuple[float, float, float, float],
        confidence: float,
        evidence: Metadata = (),
    ) -> LayoutParserDetection:
        """Create one stable raw detection from isolated inference output."""
        box = LayoutValueValidation.require_box(
            "bounding_box_pixels", bounding_box_pixels
        )
        score = LayoutValueValidation.require_ratio("confidence", confidence)
        normalized_evidence = LayoutValueValidation.normalize_metadata(evidence)
        detection_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            render_id,
            label,
            box,
            score,
            normalized_evidence,
        )
        return cls(
            detection_id=detection_id,
            render_id=render_id,
            label=label,
            bounding_box_pixels=box,
            confidence=score,
            evidence=normalized_evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported LayoutParser detection contract")
        LayoutValueValidation.require_text("render_id", self.render_id)
        LayoutValueValidation.require_text("label", self.label)
        box = LayoutValueValidation.require_box(
            "bounding_box_pixels", self.bounding_box_pixels
        )
        object.__setattr__(self, "bounding_box_pixels", box)
        score = LayoutValueValidation.require_ratio(
            "confidence", self.confidence
        )
        object.__setattr__(self, "confidence", score)
        evidence = LayoutValueValidation.normalize_metadata(self.evidence)
        object.__setattr__(self, "evidence", evidence)
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.render_id,
            self.label,
            box,
            score,
            evidence,
        )
        if self.detection_id != expected:
            raise ValueError("LayoutParser detection ID is inconsistent")

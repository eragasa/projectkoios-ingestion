"""Nominal base contracts for OCR domain objects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from projectkoios.ingestion.models import BoundingBox

if TYPE_CHECKING:
    from projectkoios.ingestion.ocr.contract.contracts import OCRConfidence


class OCRTextOutput(ABC):
    """Nominal base for source-linked OCR text returned by factories."""

    __slots__ = ()

    selection_id: str
    image_id: str
    pixel_coordinate_system: str
    source_coordinate_system: str
    text: str
    pixel_bounding_box: BoundingBox
    source_bounding_box: BoundingBox
    confidence: OCRConfidence | None
    order: int
    warning_ids: tuple[str, ...]
    configuration_digest: str
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str

    @property
    @abstractmethod
    def output_id(self) -> str:
        """Return the concrete output's stable identity."""

    def _validate_common_contract(self) -> None:
        """Validate invariants shared by every OCR text output."""
        from projectkoios.ingestion.ocr.contract.contracts import (
            _MAX_TEXT_CHARACTERS_PER_ITEM,
            PIXEL_COORDINATE_SYSTEM,
            OCRContract,
        )
        from projectkoios.ingestion.pdf.models import (
            PYMUPDF_COORDINATE_SYSTEM,
        )

        OCRContract._require_identity_fields(
            self.selection_id,
            self.image_id,
            self.configuration_digest,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        if self.pixel_coordinate_system != PIXEL_COORDINATE_SYSTEM:
            raise ValueError("OCR pixel coordinate system is unsupported")
        if self.source_coordinate_system != PYMUPDF_COORDINATE_SYSTEM:
            raise ValueError("OCR source coordinate system is unsupported")
        OCRContract._hard_bounded_string(
            "OCR output text",
            self.text,
            nonempty=True,
            limit=_MAX_TEXT_CHARACTERS_PER_ITEM,
        )
        object.__setattr__(
            self,
            "pixel_bounding_box",
            OCRContract._finite_box(
                self.pixel_bounding_box, "pixel_bounding_box"
            ),
        )
        object.__setattr__(
            self,
            "source_bounding_box",
            OCRContract._finite_box(
                self.source_bounding_box, "source_bounding_box"
            ),
        )
        OCRContract._validate_confidence(self.confidence)
        OCRContract._nonnegative_integer("order", self.order)
        OCRContract._require_unique_strings("warning_ids", self.warning_ids)

"""OCRLine OCR domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.models import BoundingBox
from projectkoios.ingestion.ocr import _geometry as geometry
from projectkoios.ingestion.ocr import _identity as identity
from projectkoios.ingestion.ocr import _primitives as primitives
from projectkoios.ingestion.ocr.base import OCRTextOutput
from projectkoios.ingestion.ocr.confidence import OCRConfidence
from projectkoios.ingestion.ocr.configuration import OCRConfiguration
from projectkoios.ingestion.ocr.constants import PIXEL_COORDINATE_SYSTEM
from projectkoios.ingestion.ocr.selection import OCRSelection


@dataclass(frozen=True)
class OCRLine(AbstractImmutableDataObject, OCRTextOutput):
    """One ordered OCR line, optionally retaining ordered token membership."""

    line_id: str
    selection_id: str
    image_id: str
    pixel_coordinate_system: str
    source_coordinate_system: str
    text: str
    pixel_bounding_box: BoundingBox
    source_bounding_box: BoundingBox
    confidence: OCRConfidence | None
    order: int
    token_ids: tuple[str, ...]
    warning_ids: tuple[str, ...]
    configuration_digest: str
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str

    @classmethod
    def create(
        cls,
        *,
        selection: OCRSelection,
        configuration: OCRConfiguration,
        text: str,
        pixel_bounding_box: BoundingBox,
        confidence: OCRConfidence | None,
        order: int,
        token_ids: tuple[str, ...] = (),
        warning_ids: tuple[str, ...] = (),
        processor_name: str,
        processor_version: str,
        backend_name: str,
        backend_version: str,
    ) -> OCRLine:
        primitives._bounded_string(
            "line text",
            text,
            configuration.max_text_characters_per_item,
            nonempty=True,
        )
        pixel_box = geometry._pixel_box(selection.image, pixel_bounding_box)
        source_box = geometry._map_pixel_box(selection.image, pixel_box)
        primitives._validate_confidence(confidence)
        primitives._nonnegative_integer("order", order)
        primitives._require_unique_strings("token_ids", token_ids)
        primitives._require_unique_strings("warning_ids", warning_ids)
        primitives._require_identity_fields(
            selection.selection_id,
            selection.image.image_id,
            configuration.configuration_digest,
            processor_name,
            processor_version,
            backend_name,
            backend_version,
        )
        line_id = identity._ocr_line_id(
            selection.selection_id,
            selection.image.image_id,
            text,
            pixel_box,
            source_box,
            confidence,
            order,
            token_ids,
            warning_ids,
            configuration.configuration_digest,
            processor_name,
            processor_version,
            backend_name,
            backend_version,
        )
        return cls(
            line_id=line_id,
            selection_id=selection.selection_id,
            image_id=selection.image.image_id,
            pixel_coordinate_system=PIXEL_COORDINATE_SYSTEM,
            source_coordinate_system=(
                selection.image.rendered_region.coordinate_system
            ),
            text=text,
            pixel_bounding_box=pixel_box,
            source_bounding_box=source_box,
            confidence=confidence,
            order=order,
            token_ids=token_ids,
            warning_ids=warning_ids,
            configuration_digest=configuration.configuration_digest,
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
        )

    @property
    def output_id(self) -> str:
        return self.line_id

    def __post_init__(self) -> None:
        self._validate_common_contract()
        primitives._require_unique_strings("token_ids", self.token_ids)
        expected = identity._ocr_line_id(
            self.selection_id,
            self.image_id,
            self.text,
            self.pixel_bounding_box,
            self.source_bounding_box,
            self.confidence,
            self.order,
            self.token_ids,
            self.warning_ids,
            self.configuration_digest,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        if self.line_id != expected:
            raise ValueError("OCR line ID does not match its evidence")

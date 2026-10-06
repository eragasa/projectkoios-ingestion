"""OCRPageImage OCR domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.constants import OCR_CONTRACT_VERSION
from projectkoios.ingestion.ocr.identity import derivation as identity
from projectkoios.ingestion.pdf.models import RenderedRegion


@dataclass(frozen=True)
class OCRPageImage(AbstractImmutableDataObject):
    """An OCR image that retains one exact validated RenderedRegion."""

    image_id: str
    rendered_region: RenderedRegion
    contract_version: str = OCR_CONTRACT_VERSION

    @classmethod
    def from_rendered_region(cls, region: RenderedRegion) -> OCRPageImage:
        return cls(
            image_id=identity._ocr_image_id(region),
            rendered_region=region,
        )

    def __post_init__(self) -> None:
        if self.contract_version != OCR_CONTRACT_VERSION:
            raise ValueError("unsupported OCR image contract version")
        if not isinstance(self.rendered_region, RenderedRegion):
            raise TypeError("rendered_region must be a RenderedRegion")
        if self.image_id != identity._ocr_image_id(self.rendered_region):
            raise ValueError("OCR image ID does not match rendered evidence")

    def identity_parts(self) -> tuple[object, ...]:
        return identity._image_identity_parts(self.rendered_region)

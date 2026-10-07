"""Frozen rendered-page evidence for layout review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.limits.definition import (
    MAX_LAYOUT_PAGE_INDEX,
)
from projectkoios.ingestion.layout.render.mapping import LayoutPixelMapping
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class LayoutPageRenderEvidence(AbstractImmutableDataObject):
    """Reference exact page pixels and mapping without retaining image bytes."""

    CONTRACT_NAME: ClassVar[str] = "layout-page-render-evidence"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    render_id: str
    source_id: str
    source_blob_id: str
    page_index: int
    mapping: LayoutPixelMapping
    image_media_type: str
    image_sha256: SHA256Hash
    renderer_name: str
    renderer_version: str
    backend_name: str
    backend_version: str
    renderer_configuration_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        source_blob_id: str,
        page_index: int,
        mapping: LayoutPixelMapping,
        image_media_type: str,
        image_sha256: str,
        renderer_name: str,
        renderer_version: str,
        backend_name: str,
        backend_version: str,
        renderer_configuration_id: str,
    ) -> LayoutPageRenderEvidence:
        """Create one bounded rendered-page identity independent of analysis."""
        values = cls.validated_values(
            source_id=source_id,
            source_blob_id=source_blob_id,
            page_index=page_index,
            mapping=mapping,
            image_media_type=image_media_type,
            image_sha256=image_sha256,
            renderer_name=renderer_name,
            renderer_version=renderer_version,
            backend_name=backend_name,
            backend_version=backend_version,
            renderer_configuration_id=renderer_configuration_id,
        )
        render_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            *values,
        )
        return cls(
            render_id=render_id,
            source_id=values[0],
            source_blob_id=values[1],
            page_index=values[2],
            mapping=values[3],
            image_media_type=values[4],
            image_sha256=values[5],
            renderer_name=values[6],
            renderer_version=values[7],
            backend_name=values[8],
            backend_version=values[9],
            renderer_configuration_id=values[10],
        )

    @classmethod
    def validated_values(
        cls,
        *,
        source_id: object,
        source_blob_id: object,
        page_index: object,
        mapping: object,
        image_media_type: object,
        image_sha256: object,
        renderer_name: object,
        renderer_version: object,
        backend_name: object,
        backend_version: object,
        renderer_configuration_id: object,
    ) -> tuple[
        str,
        str,
        int,
        LayoutPixelMapping,
        str,
        SHA256Hash,
        str,
        str,
        str,
        str,
        str,
    ]:
        """Validate every persisted render-evidence field before hashing."""
        source = LayoutValueValidation.require_text("source_id", source_id)
        blob = LayoutValueValidation.require_text(
            "source_blob_id", source_blob_id
        )
        index = LayoutValueValidation.require_nonnegative_integer(
            "page_index", page_index, maximum=MAX_LAYOUT_PAGE_INDEX
        )
        if type(mapping) is not LayoutPixelMapping:
            raise TypeError("mapping must be LayoutPixelMapping")
        media_type = LayoutValueValidation.require_text(
            "image_media_type", image_media_type
        )
        if not media_type.startswith("image/"):
            raise ValueError("image_media_type must identify an image")
        if not SHA256Hash.is_canonical(image_sha256):
            raise ValueError("image_sha256 must be a canonical SHA-256")
        digest = SHA256Hash(image_sha256)
        renderer = LayoutValueValidation.require_text(
            "renderer_name", renderer_name
        )
        renderer_release = LayoutValueValidation.require_text(
            "renderer_version", renderer_version
        )
        backend = LayoutValueValidation.require_text(
            "backend_name", backend_name
        )
        backend_release = LayoutValueValidation.require_text(
            "backend_version", backend_version
        )
        configuration = LayoutValueValidation.require_text(
            "renderer_configuration_id", renderer_configuration_id
        )
        return (
            source,
            blob,
            index,
            mapping,
            media_type,
            digest,
            renderer,
            renderer_release,
            backend,
            backend_release,
            configuration,
        )

    @property
    def image_width(self) -> int:
        """Return mapped raster width for proposal-bound validation."""
        return self.mapping.image_width

    @property
    def image_height(self) -> int:
        """Return mapped raster height for proposal-bound validation."""
        return self.mapping.image_height

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout render evidence contract")
        values = self.validated_values(
            source_id=self.source_id,
            source_blob_id=self.source_blob_id,
            page_index=self.page_index,
            mapping=self.mapping,
            image_media_type=self.image_media_type,
            image_sha256=self.image_sha256,
            renderer_name=self.renderer_name,
            renderer_version=self.renderer_version,
            backend_name=self.backend_name,
            backend_version=self.backend_version,
            renderer_configuration_id=self.renderer_configuration_id,
        )
        object.__setattr__(self, "image_sha256", values[5])
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            *values,
        )
        if self.render_id != expected:
            raise ValueError("layout render evidence ID is inconsistent")

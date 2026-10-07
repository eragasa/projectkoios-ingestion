"""Frozen rendered-page evidence for layout review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.contracts import PageLayoutResult
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class LayoutPageRenderEvidence(AbstractImmutableDataObject):
    """Reference exact page pixels without retaining private image bytes."""

    CONTRACT_NAME: ClassVar[str] = "layout-page-render-evidence"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    render_id: str
    layout_result_id: str
    source_id: str
    source_blob_id: str
    page_index: int
    page_coordinate_system: str
    image_width: int
    image_height: int
    image_media_type: str
    image_sha256: SHA256Hash
    renderer_name: str
    renderer_version: str
    renderer_configuration_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        layout: PageLayoutResult,
        image_width: int,
        image_height: int,
        image_media_type: str,
        image_sha256: str,
        renderer_name: str,
        renderer_version: str,
        renderer_configuration_id: str,
    ) -> LayoutPageRenderEvidence:
        """Bind one immutable image identity to an analyzed source page."""
        if type(layout) is not PageLayoutResult:
            raise TypeError("layout must be PageLayoutResult")
        digest = SHA256Hash(image_sha256)
        render_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            layout.result_id,
            layout.source_id,
            layout.source_blob_id,
            layout.page_index,
            layout.coordinate_system,
            image_width,
            image_height,
            image_media_type,
            digest,
            renderer_name,
            renderer_version,
            renderer_configuration_id,
        )
        return cls(
            render_id=render_id,
            layout_result_id=layout.result_id,
            source_id=layout.source_id,
            source_blob_id=layout.source_blob_id,
            page_index=layout.page_index,
            page_coordinate_system=layout.coordinate_system,
            image_width=image_width,
            image_height=image_height,
            image_media_type=image_media_type,
            image_sha256=digest,
            renderer_name=renderer_name,
            renderer_version=renderer_version,
            renderer_configuration_id=renderer_configuration_id,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout render evidence contract")
        LayoutValueValidation.require_text(
            "layout_result_id", self.layout_result_id
        )
        LayoutValueValidation.require_text("source_id", self.source_id)
        LayoutValueValidation.require_text(
            "source_blob_id", self.source_blob_id
        )
        if (
            isinstance(self.page_index, bool)
            or not isinstance(self.page_index, int)
            or self.page_index < 0
        ):
            raise ValueError("page_index must be a non-negative integer")
        LayoutValueValidation.require_text(
            "page_coordinate_system", self.page_coordinate_system
        )
        LayoutValueValidation.require_positive_integer(
            "image_width", self.image_width
        )
        LayoutValueValidation.require_positive_integer(
            "image_height", self.image_height
        )
        media_type = LayoutValueValidation.require_text(
            "image_media_type", self.image_media_type
        )
        if not media_type.startswith("image/"):
            raise ValueError("image_media_type must identify an image")
        digest = SHA256Hash(self.image_sha256)
        object.__setattr__(self, "image_sha256", digest)
        LayoutValueValidation.require_text("renderer_name", self.renderer_name)
        LayoutValueValidation.require_text(
            "renderer_version", self.renderer_version
        )
        LayoutValueValidation.require_text(
            "renderer_configuration_id", self.renderer_configuration_id
        )
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.layout_result_id,
            self.source_id,
            self.source_blob_id,
            self.page_index,
            self.page_coordinate_system,
            self.image_width,
            self.image_height,
            self.image_media_type,
            digest,
            self.renderer_name,
            self.renderer_version,
            self.renderer_configuration_id,
        )
        if self.render_id != expected:
            raise ValueError("layout render evidence ID is inconsistent")

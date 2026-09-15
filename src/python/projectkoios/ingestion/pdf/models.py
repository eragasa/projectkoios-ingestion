from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from enum import StrEnum

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import BoundingBox, SourceDocument

PYMUPDF_COORDINATE_SYSTEM = "pymupdf_unrotated_cropbox_points_top_left"
PNG_MEDIA_TYPE = "image/png"
PIXEL_ROUNDING_CONVENTION = "scaled_display_clip_outward_to_integer_pixels"
PixelToSourceMatrix = tuple[float, float, float, float, float, float]


class RegionColorMode(StrEnum):
    """Opaque PDF raster color behavior."""

    RGB = "rgb"
    GRAYSCALE = "grayscale"


@dataclass(frozen=True)
class PageRegionSelection:
    """One explicit full-page or rectangular PDF rendering selection."""

    source_id: str
    source_blob_id: str
    page_index: int
    full_page: bool
    bounding_box: BoundingBox | None
    coordinate_system: str = PYMUPDF_COORDINATE_SYSTEM

    @classmethod
    def for_full_page(
        cls,
        source: SourceDocument,
        page_index: int,
    ) -> PageRegionSelection:
        return cls(
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            page_index=page_index,
            full_page=True,
            bounding_box=None,
        )

    @classmethod
    def for_bounding_box(
        cls,
        source: SourceDocument,
        page_index: int,
        bounding_box: BoundingBox,
    ) -> PageRegionSelection:
        return cls(
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            page_index=page_index,
            full_page=False,
            bounding_box=bounding_box,
        )

    def __post_init__(self) -> None:
        if not self.source_id or not self.source_blob_id:
            raise ValueError(
                "region selection source identity must be complete"
            )
        if (
            isinstance(self.page_index, bool)
            or not isinstance(self.page_index, int)
            or self.page_index < 0
        ):
            raise ValueError("page_index must be a non-negative integer")
        if not isinstance(self.full_page, bool):
            raise ValueError("full_page must be a boolean")
        if self.coordinate_system != PYMUPDF_COORDINATE_SYSTEM:
            raise ValueError(
                "region selection coordinate system must be "
                f"{PYMUPDF_COORDINATE_SYSTEM}"
            )
        if self.full_page:
            if self.bounding_box is not None:
                raise ValueError(
                    "a full-page selection must not declare a bounding box"
                )
            return
        if self.bounding_box is None:
            raise ValueError(
                "a bounded selection must declare a bounding box; use "
                "full_page=True explicitly for a whole page"
            )
        object.__setattr__(
            self,
            "bounding_box",
            _validated_bounding_box(self.bounding_box),
        )

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.source_id,
            self.source_blob_id,
            self.page_index,
            self.full_page,
            self.bounding_box,
            self.coordinate_system,
        )


@dataclass(frozen=True)
class RegionRenderConfiguration:
    """Rendering behavior and deterministic pre-allocation limits."""

    resolution_dpi: int = 144
    color_mode: RegionColorMode = RegionColorMode.RGB
    max_selections: int = 256
    max_dimension_pixels: int = 16_384
    max_pixels: int = 25_000_000
    max_raster_bytes: int = 100_000_000
    max_total_pixels: int = 25_000_000
    max_total_raster_bytes: int = 100_000_000

    def __post_init__(self) -> None:
        integer_fields = (
            ("resolution_dpi", self.resolution_dpi),
            ("max_selections", self.max_selections),
            ("max_dimension_pixels", self.max_dimension_pixels),
            ("max_pixels", self.max_pixels),
            ("max_raster_bytes", self.max_raster_bytes),
            ("max_total_pixels", self.max_total_pixels),
            ("max_total_raster_bytes", self.max_total_raster_bytes),
        )
        for name, value in integer_fields:
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.color_mode, RegionColorMode):
            try:
                object.__setattr__(
                    self,
                    "color_mode",
                    RegionColorMode(self.color_mode),
                )
            except ValueError as error:
                raise ValueError(
                    "unsupported region render color mode"
                ) from error

    @property
    def configuration_digest(self) -> str:
        return stable_id(
            "configuration",
            {
                "resolution_dpi": self.resolution_dpi,
                "color_mode": self.color_mode.value,
                "alpha": False,
                "background": "white",
                "max_selections": self.max_selections,
                "max_dimension_pixels": self.max_dimension_pixels,
                "max_pixels": self.max_pixels,
                "max_raster_bytes": self.max_raster_bytes,
                "max_total_pixels": self.max_total_pixels,
                "max_total_raster_bytes": self.max_total_raster_bytes,
            },
        )


@dataclass(frozen=True)
class RenderedRegion:
    """Destination-independent PNG bytes and complete rendering evidence."""

    region_id: str
    source_id: str
    source_blob_id: str
    source_content_hash: str
    page_index: int
    printed_page_label: str | None
    source_bounding_box: BoundingBox
    effective_source_bounding_box: BoundingBox
    pixel_to_source_matrix: PixelToSourceMatrix
    pixel_rounding: str
    page_rotation_degrees: int
    selection_was_full_page: bool
    coordinate_system: str
    resolution_dpi: int
    color_mode: RegionColorMode
    alpha: bool
    media_type: str
    byte_length: int
    width_pixels: int
    height_pixels: int
    content_sha256: str
    content: bytes
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    configuration_digest: str

    @classmethod
    def create(
        cls,
        *,
        source: SourceDocument,
        page_index: int,
        printed_page_label: str | None,
        source_bounding_box: BoundingBox,
        effective_source_bounding_box: BoundingBox,
        pixel_to_source_matrix: PixelToSourceMatrix,
        page_rotation_degrees: int,
        selection_was_full_page: bool,
        configuration: RegionRenderConfiguration,
        content: bytes,
        width_pixels: int,
        height_pixels: int,
        processor_name: str,
        processor_version: str,
        backend_name: str,
        backend_version: str,
    ) -> RenderedRegion:
        bounding_box = _validated_bounding_box(source_bounding_box)
        effective_box = _validated_effective_bounding_box(
            effective_source_bounding_box
        )
        transform = _validated_pixel_to_source_matrix(pixel_to_source_matrix)
        content_sha256 = hashlib.sha256(content).hexdigest()
        region_id = _rendered_region_id(
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            page_index=page_index,
            selection_was_full_page=selection_was_full_page,
            source_bounding_box=bounding_box,
            effective_source_bounding_box=effective_box,
            pixel_to_source_matrix=transform,
            page_rotation_degrees=page_rotation_degrees,
            resolution_dpi=configuration.resolution_dpi,
            color_mode=configuration.color_mode,
            configuration_digest=configuration.configuration_digest,
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
            content_sha256=content_sha256,
        )
        return cls(
            region_id=region_id,
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            source_content_hash=source.content_hash,
            page_index=page_index,
            printed_page_label=printed_page_label,
            source_bounding_box=bounding_box,
            effective_source_bounding_box=effective_box,
            pixel_to_source_matrix=transform,
            pixel_rounding=PIXEL_ROUNDING_CONVENTION,
            page_rotation_degrees=page_rotation_degrees,
            selection_was_full_page=selection_was_full_page,
            coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
            resolution_dpi=configuration.resolution_dpi,
            color_mode=configuration.color_mode,
            alpha=False,
            media_type=PNG_MEDIA_TYPE,
            byte_length=len(content),
            width_pixels=width_pixels,
            height_pixels=height_pixels,
            content_sha256=content_sha256,
            content=content,
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
            configuration_digest=configuration.configuration_digest,
        )

    def __post_init__(self) -> None:
        if not self.source_id or not self.source_blob_id:
            raise ValueError("rendered region source identity must be complete")
        if len(self.source_content_hash) != 64:
            raise ValueError(
                "rendered region source hash must be a SHA-256 hex digest"
            )
        try:
            int(self.source_content_hash, 16)
        except ValueError as error:
            raise ValueError(
                "rendered region source hash must be a SHA-256 hex digest"
            ) from error
        if self.source_blob_id != f"blob:sha256:{self.source_content_hash}":
            raise ValueError("rendered region blob and content hash must agree")
        if (
            isinstance(self.page_index, bool)
            or not isinstance(self.page_index, int)
            or self.page_index < 0
        ):
            raise ValueError("page_index must be a non-negative integer")
        if not isinstance(self.selection_was_full_page, bool):
            raise ValueError("selection_was_full_page must be a boolean")
        source_bounding_box = _validated_bounding_box(self.source_bounding_box)
        effective_source_bounding_box = _validated_effective_bounding_box(
            self.effective_source_bounding_box
        )
        pixel_to_source_matrix = _validated_pixel_to_source_matrix(
            self.pixel_to_source_matrix
        )
        object.__setattr__(self, "source_bounding_box", source_bounding_box)
        object.__setattr__(
            self,
            "effective_source_bounding_box",
            effective_source_bounding_box,
        )
        object.__setattr__(
            self,
            "pixel_to_source_matrix",
            pixel_to_source_matrix,
        )
        if self.pixel_rounding != PIXEL_ROUNDING_CONVENTION:
            raise ValueError("rendered region pixel rounding is unsupported")
        if (
            isinstance(self.page_rotation_degrees, bool)
            or not isinstance(self.page_rotation_degrees, int)
            or self.page_rotation_degrees not in (0, 90, 180, 270)
        ):
            raise ValueError("page rotation must be 0, 90, 180, or 270")
        if self.coordinate_system != PYMUPDF_COORDINATE_SYSTEM:
            raise ValueError("rendered region coordinate system is unsupported")
        if (
            isinstance(self.resolution_dpi, bool)
            or not isinstance(self.resolution_dpi, int)
            or self.resolution_dpi <= 0
        ):
            raise ValueError("resolution_dpi must be a positive integer")
        if not isinstance(self.color_mode, RegionColorMode):
            raise ValueError("rendered region color mode is unsupported")
        if not isinstance(self.alpha, bool):
            raise ValueError("alpha must be a boolean")
        if self.alpha:
            raise ValueError("rendered regions must use opaque PNG output")
        if self.media_type != PNG_MEDIA_TYPE:
            raise ValueError("rendered region media type must be image/png")
        if self.byte_length != len(self.content):
            raise ValueError(
                "rendered region byte length does not match content"
            )
        if hashlib.sha256(self.content).hexdigest() != self.content_sha256:
            raise ValueError(
                "rendered region content hash does not match content"
            )
        if self.width_pixels <= 0 or self.height_pixels <= 0:
            raise ValueError(
                "rendered region pixel dimensions must be positive"
            )
        expected_effective_box = _effective_box_from_transform(
            pixel_to_source_matrix,
            self.width_pixels,
            self.height_pixels,
        )
        if effective_source_bounding_box != expected_effective_box:
            raise ValueError(
                "effective source box does not match pixel transform"
            )
        if len(self.content_sha256) != 64:
            raise ValueError(
                "rendered region content hash must be a SHA-256 hex digest"
            )
        if not self.content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("rendered region content must be PNG bytes")
        if len(self.content) < 24 or self.content[12:16] != b"IHDR":
            raise ValueError("rendered region content has no PNG IHDR")
        png_width = int.from_bytes(self.content[16:20], "big")
        png_height = int.from_bytes(self.content[20:24], "big")
        png_color_type = self.content[25]
        expected_color_type = 2 if self.color_mode is RegionColorMode.RGB else 0
        if png_color_type != expected_color_type:
            raise ValueError(
                "rendered region PNG color type does not match evidence"
            )
        if (png_width, png_height) != (
            self.width_pixels,
            self.height_pixels,
        ):
            raise ValueError(
                "rendered region PNG dimensions do not match evidence"
            )
        identity_fields = (
            self.region_id,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
            self.configuration_digest,
        )
        if any(not value for value in identity_fields):
            raise ValueError(
                "rendered region processor identity must be complete"
            )
        expected_region_id = _rendered_region_id(
            source_id=self.source_id,
            source_blob_id=self.source_blob_id,
            page_index=self.page_index,
            selection_was_full_page=self.selection_was_full_page,
            source_bounding_box=source_bounding_box,
            effective_source_bounding_box=effective_source_bounding_box,
            pixel_to_source_matrix=pixel_to_source_matrix,
            page_rotation_degrees=self.page_rotation_degrees,
            resolution_dpi=self.resolution_dpi,
            color_mode=self.color_mode,
            configuration_digest=self.configuration_digest,
            processor_name=self.processor_name,
            processor_version=self.processor_version,
            backend_name=self.backend_name,
            backend_version=self.backend_version,
            content_sha256=self.content_sha256,
        )
        if self.region_id != expected_region_id:
            raise ValueError("rendered region ID does not match its evidence")


def _validated_bounding_box(bounding_box: BoundingBox) -> BoundingBox:
    if len(bounding_box) != 4:
        raise ValueError("bounding_box must contain four coordinates")
    coordinates = _validated_finite_coordinates(bounding_box, length=4)
    x0, y0, x1, y1 = coordinates
    if x0 < 0 or y0 < 0:
        raise ValueError("bounding_box coordinates must be non-negative")
    if x1 <= x0 or y1 <= y0:
        raise ValueError(
            "bounding_box must have positive area and ordered coordinates"
        )
    return (x0, y0, x1, y1)


def _validated_effective_bounding_box(
    bounding_box: BoundingBox,
) -> BoundingBox:
    coordinates = _validated_finite_coordinates(bounding_box, length=4)
    x0, y0, x1, y1 = coordinates
    if x1 <= x0 or y1 <= y0:
        raise ValueError(
            "effective_source_bounding_box must have positive area and "
            "ordered coordinates"
        )
    return (x0, y0, x1, y1)


def _validated_pixel_to_source_matrix(
    transform: PixelToSourceMatrix,
) -> PixelToSourceMatrix:
    coordinates = _validated_finite_coordinates(transform, length=6)
    a, b, c, d, e, f = coordinates
    determinant = a * d - b * c
    if determinant == 0:
        raise ValueError("pixel_to_source_matrix must be invertible")
    return (a, b, c, d, e, f)


def _validated_finite_coordinates(
    coordinates: tuple[float, ...],
    *,
    length: int,
) -> tuple[float, ...]:
    if len(coordinates) != length:
        raise ValueError(f"coordinates must contain {length} values")
    normalized: list[float] = []
    for coordinate in coordinates:
        if isinstance(coordinate, bool) or not isinstance(
            coordinate, int | float
        ):
            raise ValueError("coordinates must be finite numbers")
        try:
            value = float(coordinate)
        except OverflowError as error:
            raise ValueError("coordinates must be finite numbers") from error
        if not math.isfinite(value):
            raise ValueError("coordinates must be finite numbers")
        normalized.append(0.0 if value == 0.0 else value)
    return tuple(normalized)


def _effective_box_from_transform(
    transform: PixelToSourceMatrix,
    width_pixels: int,
    height_pixels: int,
) -> BoundingBox:
    a, b, c, d, e, f = transform
    corners = (
        (e, f),
        (width_pixels * a + e, width_pixels * b + f),
        (height_pixels * c + e, height_pixels * d + f),
        (
            width_pixels * a + height_pixels * c + e,
            width_pixels * b + height_pixels * d + f,
        ),
    )
    xs = tuple(point[0] for point in corners)
    ys = tuple(point[1] for point in corners)
    return (min(xs), min(ys), max(xs), max(ys))


def _rendered_region_id(
    *,
    source_id: str,
    source_blob_id: str,
    page_index: int,
    selection_was_full_page: bool,
    source_bounding_box: BoundingBox,
    effective_source_bounding_box: BoundingBox,
    pixel_to_source_matrix: PixelToSourceMatrix,
    page_rotation_degrees: int,
    resolution_dpi: int,
    color_mode: RegionColorMode,
    configuration_digest: str,
    processor_name: str,
    processor_version: str,
    backend_name: str,
    backend_version: str,
    content_sha256: str,
) -> str:
    return stable_id(
        "rendered-region",
        source_id,
        source_blob_id,
        page_index,
        selection_was_full_page,
        source_bounding_box,
        effective_source_bounding_box,
        pixel_to_source_matrix,
        PIXEL_ROUNDING_CONVENTION,
        page_rotation_degrees,
        PYMUPDF_COORDINATE_SYSTEM,
        resolution_dpi,
        color_mode.value,
        False,
        configuration_digest,
        processor_name,
        processor_version,
        backend_name,
        backend_version,
        content_sha256,
    )

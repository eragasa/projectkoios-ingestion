from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import islice
from typing import Any, BinaryIO

from projectkoios.ingestion.base import BasePageRegionRenderer
from projectkoios.ingestion.models import BoundingBox, SourceDocument
from projectkoios.ingestion.pdf.extractor import PdfDependencyUnavailableError
from projectkoios.ingestion.pdf.models import (
    PageRegionSelection,
    PixelToSourceMatrix,
    RegionColorMode,
    RegionRenderConfiguration,
    RenderedRegion,
)


class PdfRegionRenderLimitError(ValueError):
    """Raised before raster allocation when a configured limit is exceeded."""


@dataclass(frozen=True)
class _RenderPlan:
    selection: PageRegionSelection
    source_bounding_box: BoundingBox
    effective_source_bounding_box: BoundingBox
    pixel_to_source_matrix: PixelToSourceMatrix
    display_clip: tuple[float, float, float, float]
    page_rotation_degrees: int
    printed_page_label: str | None
    width_pixels: int
    height_pixels: int
    device_x: int
    device_y: int


class PyMuPdfRegionRenderer(BasePageRegionRenderer):
    """Render only explicitly selected PDF pages or regions to PNG bytes."""

    name = "pymupdf-region-renderer"
    version = "1"
    backend_name = "pymupdf"

    def __init__(
        self,
        *,
        resolution_dpi: int = 144,
        color_mode: RegionColorMode = RegionColorMode.RGB,
        max_selections: int = 256,
        max_dimension_pixels: int = 16_384,
        max_pixels: int = 25_000_000,
        max_raster_bytes: int = 100_000_000,
        max_total_pixels: int = 25_000_000,
        max_total_raster_bytes: int = 100_000_000,
    ) -> None:
        self.configuration = RegionRenderConfiguration(
            resolution_dpi=resolution_dpi,
            color_mode=color_mode,
            max_selections=max_selections,
            max_dimension_pixels=max_dimension_pixels,
            max_pixels=max_pixels,
            max_raster_bytes=max_raster_bytes,
            max_total_pixels=max_total_pixels,
            max_total_raster_bytes=max_total_raster_bytes,
        )

    @property
    def configuration_digest(self) -> str:
        return self.configuration.configuration_digest

    def render(
        self,
        source: SourceDocument,
        content: BinaryIO,
        selections: Iterable[PageRegionSelection],
    ) -> tuple[RenderedRegion, ...]:
        requested = self._bounded_selections(selections)
        self._validate_request(source, requested)
        try:
            import pymupdf
        except ImportError as error:  # pragma: no cover - environment dependent
            raise PdfDependencyUnavailableError(
                "PDF region rendering requires the 'pdf' project extra"
            ) from error

        payload = content.read()
        self._validate_source(source, payload)
        document = pymupdf.open(stream=payload, filetype="pdf")
        try:
            if document.needs_pass:
                raise ValueError("encrypted PDF requires a password")
            self._validate_page_indices(requested, document.page_count)
            plans = self._build_plans(pymupdf, document, requested)
            self._check_aggregate_limits(plans)
            backend_version = self._backend_version(pymupdf)
            rendered_by_selection: dict[
                PageRegionSelection, RenderedRegion
            ] = {}
            for plan in plans:
                rendered_by_selection[plan.selection] = self._render_plan(
                    pymupdf,
                    document,
                    source,
                    plan,
                    backend_version,
                )
            return tuple(
                rendered_by_selection[selection] for selection in requested
            )
        finally:
            document.close()

    def _bounded_selections(
        self,
        selections: Iterable[PageRegionSelection],
    ) -> tuple[PageRegionSelection, ...]:
        requested = tuple(
            islice(selections, self.configuration.max_selections + 1)
        )
        if len(requested) > self.configuration.max_selections:
            raise PdfRegionRenderLimitError(
                "region selection count exceeds max_selections "
                f"({self.configuration.max_selections})"
            )
        return requested

    def _validate_request(
        self,
        source: SourceDocument,
        requested: tuple[PageRegionSelection, ...],
    ) -> None:
        if source.media_type != "application/pdf":
            raise ValueError("PyMuPdfRegionRenderer requires application/pdf")
        if not requested:
            raise ValueError("at least one page region selection is required")
        for selection in requested:
            if not isinstance(selection, PageRegionSelection):
                raise TypeError(
                    "selections must contain PageRegionSelection values"
                )
            if (
                selection.source_id != source.source_id
                or selection.source_blob_id != source.blob_id
            ):
                raise ValueError(
                    "region selection does not refer to the exact source"
                )

    @staticmethod
    def _validate_page_indices(
        requested: tuple[PageRegionSelection, ...],
        page_count: int,
    ) -> None:
        for selection in requested:
            if selection.page_index >= page_count:
                raise ValueError(
                    "region selection page_index is outside the PDF: "
                    f"{selection.page_index}"
                )

    def _build_plans(
        self,
        pymupdf: Any,
        document: Any,
        requested: tuple[PageRegionSelection, ...],
    ) -> tuple[_RenderPlan, ...]:
        plans: list[_RenderPlan] = []
        seen: set[PageRegionSelection] = set()
        for selection in requested:
            if selection in seen:
                continue
            seen.add(selection)
            page: Any = document.load_page(selection.page_index)
            try:
                page_width = float(page.cropbox.width)
                page_height = float(page.cropbox.height)
                if (
                    not math.isfinite(page_width)
                    or not math.isfinite(page_height)
                    or page_width <= 0
                    or page_height <= 0
                ):
                    raise ValueError(
                        "PDF page crop box must have positive area"
                    )
                if selection.full_page:
                    source_box = (0.0, 0.0, page_width, page_height)
                else:
                    assert selection.bounding_box is not None
                    source_box = selection.bounding_box
                    self._validate_box_within_page(
                        source_box,
                        page_width,
                        page_height,
                    )
                display_rect = pymupdf.Rect(*source_box) * page.rotation_matrix
                display_clip = (
                    float(display_rect.x0),
                    float(display_rect.y0),
                    float(display_rect.x1),
                    float(display_rect.y1),
                )
                (
                    width_pixels,
                    height_pixels,
                    effective_source_box,
                    pixel_to_source_matrix,
                    device_x,
                    device_y,
                ) = self._pixel_geometry(
                    pymupdf,
                    page,
                    display_rect,
                )
                self._check_limits(width_pixels, height_pixels)
                raw_label = page.get_label()
                label = (
                    str(raw_label)
                    if raw_label is not None and raw_label != ""
                    else None
                )
                plans.append(
                    _RenderPlan(
                        selection=selection,
                        source_bounding_box=source_box,
                        effective_source_bounding_box=effective_source_box,
                        pixel_to_source_matrix=pixel_to_source_matrix,
                        display_clip=display_clip,
                        page_rotation_degrees=int(page.rotation),
                        printed_page_label=label,
                        width_pixels=width_pixels,
                        height_pixels=height_pixels,
                        device_x=device_x,
                        device_y=device_y,
                    )
                )
            finally:
                page = None
        return tuple(plans)

    @staticmethod
    def _validate_box_within_page(
        bounding_box: BoundingBox,
        page_width: float,
        page_height: float,
    ) -> None:
        _, _, x1, y1 = bounding_box
        if x1 > page_width or y1 > page_height:
            raise ValueError(
                "region selection bounding_box is outside the page crop box"
            )

    def _pixel_geometry(
        self,
        pymupdf: Any,
        page: Any,
        display_rect: Any,
    ) -> tuple[
        int,
        int,
        BoundingBox,
        PixelToSourceMatrix,
        int,
        int,
    ]:
        largest_point_dimension = max(
            float(display_rect.width),
            float(display_rect.height),
        )
        if (
            not math.isfinite(largest_point_dimension)
            or largest_point_dimension <= 0
        ):
            raise ValueError("region selection has no finite display area")
        try:
            maximum_dpi = (
                self.configuration.max_dimension_pixels
                * 72
                / largest_point_dimension
            )
        except OverflowError:
            maximum_dpi = math.inf
        if self.configuration.resolution_dpi > maximum_dpi:
            raise PdfRegionRenderLimitError(
                "requested DPI would exceed max_dimension_pixels before "
                "raster allocation"
            )
        try:
            scale = self.configuration.resolution_dpi / 72.0
        except OverflowError as error:
            raise PdfRegionRenderLimitError(
                "resolution_dpi cannot be represented for rasterization"
            ) from error
        pixel_rect = (display_rect * pymupdf.Matrix(scale, scale)).irect
        width_pixels = int(pixel_rect.width)
        height_pixels = int(pixel_rect.height)
        pixel_to_display = pymupdf.Matrix(
            1.0 / scale,
            0.0,
            0.0,
            1.0 / scale,
            float(pixel_rect.x0) / scale,
            float(pixel_rect.y0) / scale,
        )
        pixel_to_source = pixel_to_display * page.derotation_matrix
        transform = (
            float(pixel_to_source.a),
            float(pixel_to_source.b),
            float(pixel_to_source.c),
            float(pixel_to_source.d),
            float(pixel_to_source.e),
            float(pixel_to_source.f),
        )
        effective_source_box = self._effective_source_box(
            transform,
            width_pixels,
            height_pixels,
        )
        return (
            width_pixels,
            height_pixels,
            effective_source_box,
            transform,
            int(pixel_rect.x0),
            int(pixel_rect.y0),
        )

    @staticmethod
    def _effective_source_box(
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

    def _check_limits(self, width_pixels: int, height_pixels: int) -> None:
        if width_pixels <= 0 or height_pixels <= 0:
            raise ValueError(
                "region selection produces no pixels at the requested DPI"
            )
        largest_dimension = max(width_pixels, height_pixels)
        if largest_dimension > self.configuration.max_dimension_pixels:
            raise PdfRegionRenderLimitError(
                "rendered region dimension exceeds max_dimension_pixels "
                f"({largest_dimension} > "
                f"{self.configuration.max_dimension_pixels})"
            )
        pixels = width_pixels * height_pixels
        if pixels > self.configuration.max_pixels:
            raise PdfRegionRenderLimitError(
                "rendered region pixel count exceeds max_pixels "
                f"({pixels} > {self.configuration.max_pixels})"
            )
        channels = (
            3 if self.configuration.color_mode is RegionColorMode.RGB else 1
        )
        raster_bytes = pixels * channels
        if raster_bytes > self.configuration.max_raster_bytes:
            raise PdfRegionRenderLimitError(
                "rendered region raster size exceeds max_raster_bytes "
                f"({raster_bytes} > "
                f"{self.configuration.max_raster_bytes})"
            )

    def _check_aggregate_limits(
        self,
        plans: tuple[_RenderPlan, ...],
    ) -> None:
        total_pixels = sum(
            plan.width_pixels * plan.height_pixels for plan in plans
        )
        if total_pixels > self.configuration.max_total_pixels:
            raise PdfRegionRenderLimitError(
                "render request pixel count exceeds max_total_pixels "
                f"({total_pixels} > "
                f"{self.configuration.max_total_pixels})"
            )
        channels = (
            3 if self.configuration.color_mode is RegionColorMode.RGB else 1
        )
        total_raster_bytes = total_pixels * channels
        if total_raster_bytes > self.configuration.max_total_raster_bytes:
            raise PdfRegionRenderLimitError(
                "render request raster size exceeds max_total_raster_bytes "
                f"({total_raster_bytes} > "
                f"{self.configuration.max_total_raster_bytes})"
            )

    def _render_plan(
        self,
        pymupdf: Any,
        document: Any,
        source: SourceDocument,
        plan: _RenderPlan,
        backend_version: str,
    ) -> RenderedRegion:
        page: Any = document.load_page(plan.selection.page_index)
        pixmap: Any | None = None
        try:
            colorspace = (
                pymupdf.csRGB
                if self.configuration.color_mode is RegionColorMode.RGB
                else pymupdf.csGRAY
            )
            pixmap = page.get_pixmap(
                dpi=self.configuration.resolution_dpi,
                colorspace=colorspace,
                alpha=False,
                clip=pymupdf.Rect(*plan.display_clip),
            )
            if (
                int(pixmap.width),
                int(pixmap.height),
                int(pixmap.x),
                int(pixmap.y),
            ) != (
                plan.width_pixels,
                plan.height_pixels,
                plan.device_x,
                plan.device_y,
            ):
                raise RuntimeError(
                    "PyMuPDF raster dimensions disagreed with resource "
                    "preflight"
                )
            png = bytes(pixmap.tobytes("png"))
            return RenderedRegion.create(
                source=source,
                page_index=plan.selection.page_index,
                printed_page_label=plan.printed_page_label,
                source_bounding_box=plan.source_bounding_box,
                effective_source_bounding_box=(
                    plan.effective_source_bounding_box
                ),
                pixel_to_source_matrix=plan.pixel_to_source_matrix,
                page_rotation_degrees=plan.page_rotation_degrees,
                selection_was_full_page=plan.selection.full_page,
                configuration=self.configuration,
                content=png,
                width_pixels=plan.width_pixels,
                height_pixels=plan.height_pixels,
                processor_name=self.name,
                processor_version=self.version,
                backend_name=self.backend_name,
                backend_version=backend_version,
            )
        finally:
            pixmap = None
            page = None

    @staticmethod
    def _backend_version(pymupdf: Any) -> str:
        version = str(getattr(pymupdf, "__version__", "")).strip()
        if not version:
            raise RuntimeError("PyMuPDF does not expose its backend version")
        return version

    @staticmethod
    def _validate_source(source: SourceDocument, payload: bytes) -> None:
        digest = hashlib.sha256(payload).hexdigest()
        if digest != source.content_hash or len(payload) != source.byte_length:
            raise ValueError("source bytes do not agree with SourceDocument")

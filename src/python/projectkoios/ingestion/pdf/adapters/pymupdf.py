from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, BinaryIO

from projectkoios.ingestion.models import BoundingBox, SourceDocument
from projectkoios.ingestion.pdf.extractor import PdfDependencyUnavailableError
from projectkoios.ingestion.pdf.models import (
    PageRegionSelection,
    PixelToSourceMatrix,
    RegionColorMode,
    RegionRenderConfiguration,
    RenderedRegion,
)
from projectkoios.ingestion.pdf.preflight import (
    PdfRegionRenderPreflight,
    PdfRegionRenderPreflightPlan,
)


@dataclass(frozen=True)
class _RenderPlan:
    resources: PdfRegionRenderPreflightPlan
    source_bounding_box: BoundingBox
    effective_source_bounding_box: BoundingBox
    pixel_to_source_matrix: PixelToSourceMatrix
    display_clip: tuple[float, float, float, float]
    page_rotation_degrees: int
    printed_page_label: str | None
    device_x: int
    device_y: int


class PyMuPdfRegionRenderer:
    """Render explicitly selected PDF pages or regions through PyMuPDF."""

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
        self._preflight = PdfRegionRenderPreflight(self.configuration)

    @property
    def configuration_digest(self) -> str:
        return self.configuration.configuration_digest

    def render(
        self,
        source: SourceDocument,
        content: BinaryIO,
        selections: Iterable[PageRegionSelection],
    ) -> tuple[RenderedRegion, ...]:
        requested = self._preflight.prepare_request(source, selections)
        try:
            import pymupdf
        except ImportError as error:  # pragma: no cover - environment dependent
            raise PdfDependencyUnavailableError(
                "PDF region rendering requires the 'pdf' project extra"
            ) from error

        payload = content.read()
        self._preflight.validate_source(source, payload)
        document = pymupdf.open(stream=payload, filetype="pdf")
        try:
            if document.needs_pass:
                raise ValueError("encrypted PDF requires a password")
            self._preflight.validate_page_indices(
                requested, document.page_count
            )
            plans = self._build_plans(pymupdf, document, requested)
            self._preflight.validate_aggregate(
                tuple(plan.resources for plan in plans)
            )
            backend_version = self._backend_version(pymupdf)
            rendered_by_selection: dict[
                PageRegionSelection, RenderedRegion
            ] = {}
            for plan in plans:
                rendered_by_selection[plan.resources.selection] = (
                    self._render_plan(
                        pymupdf,
                        document,
                        source,
                        plan,
                        backend_version,
                    )
                )
            return tuple(
                rendered_by_selection[selection] for selection in requested
            )
        finally:
            document.close()

    def _build_plans(
        self,
        pymupdf: Any,
        document: Any,
        requested: tuple[PageRegionSelection, ...],
    ) -> tuple[_RenderPlan, ...]:
        plans: list[_RenderPlan] = []
        for selection in self._preflight.unique_selections(requested):
            page: Any = document.load_page(selection.page_index)
            try:
                page_width = float(page.cropbox.width)
                page_height = float(page.cropbox.height)
                self._preflight.validate_page_dimensions(
                    page_width, page_height
                )
                if selection.full_page:
                    source_box = (0.0, 0.0, page_width, page_height)
                else:
                    assert selection.bounding_box is not None
                    source_box = selection.bounding_box
                    self._preflight.validate_bounding_box(
                        source_box,
                        page_width,
                        page_height,
                    )
                requested_display_rect = (
                    pymupdf.Rect(*source_box) * page.rotation_matrix
                )
                effective_display_rect = requested_display_rect & page.rect
                if effective_display_rect.is_empty:
                    raise ValueError(
                        "region selection does not intersect the rendered page"
                    )
                display_clip = (
                    float(effective_display_rect.x0),
                    float(effective_display_rect.y0),
                    float(effective_display_rect.x1),
                    float(effective_display_rect.y1),
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
                    requested_display_rect,
                    effective_display_rect,
                )
                resources = self._preflight.plan(
                    selection,
                    width_pixels=width_pixels,
                    height_pixels=height_pixels,
                )
                raw_label = page.get_label()
                label = (
                    str(raw_label)
                    if raw_label is not None and raw_label != ""
                    else None
                )
                plans.append(
                    _RenderPlan(
                        resources=resources,
                        source_bounding_box=source_box,
                        effective_source_bounding_box=effective_source_box,
                        pixel_to_source_matrix=pixel_to_source_matrix,
                        display_clip=display_clip,
                        page_rotation_degrees=int(page.rotation),
                        printed_page_label=label,
                        device_x=device_x,
                        device_y=device_y,
                    )
                )
            finally:
                page = None
        return tuple(plans)

    def _pixel_geometry(
        self,
        pymupdf: Any,
        page: Any,
        requested_display_rect: Any,
        effective_display_rect: Any,
    ) -> tuple[
        int,
        int,
        BoundingBox,
        PixelToSourceMatrix,
        int,
        int,
    ]:
        scale = self._preflight.validate_raster_scale(
            max(
                float(requested_display_rect.width),
                float(requested_display_rect.height),
            ),
            input_units_per_inch=72.0,
        )
        pixel_rect = (
            effective_display_rect * pymupdf.Matrix(scale, scale)
        ).irect
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

    def _render_plan(
        self,
        pymupdf: Any,
        document: Any,
        source: SourceDocument,
        plan: _RenderPlan,
        backend_version: str,
    ) -> RenderedRegion:
        selection = plan.resources.selection
        page: Any = document.load_page(selection.page_index)
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
                plan.resources.width_pixels,
                plan.resources.height_pixels,
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
                page_index=selection.page_index,
                printed_page_label=plan.printed_page_label,
                source_bounding_box=plan.source_bounding_box,
                effective_source_bounding_box=(
                    plan.effective_source_bounding_box
                ),
                pixel_to_source_matrix=plan.pixel_to_source_matrix,
                page_rotation_degrees=plan.page_rotation_degrees,
                selection_was_full_page=selection.full_page,
                configuration=self.configuration,
                content=png,
                width_pixels=plan.resources.width_pixels,
                height_pixels=plan.resources.height_pixels,
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

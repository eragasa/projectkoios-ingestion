from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from projectkoios.ingestion.layout.render.evidence import (
    LayoutPageRenderEvidence,
)
from projectkoios.ingestion.layout.render.mapping import LayoutPixelMapping
from projectkoios.ingestion.models import BoundingBox
from projectkoios.ingestion.pdf.adapters.errors import (
    PdfDependencyUnavailableError,
)
from projectkoios.ingestion.pdf.models import (
    PageRegionSelection,
    PixelToSourceMatrix,
    RegionColorMode,
    RenderedRegion,
)
from projectkoios.ingestion.pdf.renderer import (
    PdfRegionRenderer,
    _PdfRegionGeometry,
)


@dataclass(frozen=True)
class _PyMuPdfDocument:
    backend: Any
    document: Any


@dataclass(frozen=True)
class _PyMuPdfExecutionState:
    page_index: int
    display_clip: tuple[float, float, float, float]
    device_x: int
    device_y: int


class PyMuPdfRegionRenderer(PdfRegionRenderer):
    """Render explicitly selected PDF pages or regions through PyMuPDF."""

    name = "pymupdf-region-renderer"
    version = "1"
    backend_name = "pymupdf"

    @classmethod
    def project_layout_render_evidence(
        cls, *, rendered_region: RenderedRegion
    ) -> LayoutPageRenderEvidence:
        """Project exact full-page renderer output into layout evidence."""
        if type(rendered_region) is not RenderedRegion:
            raise TypeError("rendered_region must be RenderedRegion")
        if (
            rendered_region.processor_name != cls.name
            or rendered_region.processor_version != cls.version
            or rendered_region.backend_name != cls.backend_name
        ):
            raise ValueError("rendered region was not produced by this adapter")
        if not rendered_region.selection_was_full_page:
            raise ValueError(
                "layout render evidence requires a full-page rendered region"
            )
        mapping = LayoutPixelMapping.create(
            source_coordinate_system=rendered_region.coordinate_system,
            requested_source_bounding_box=(rendered_region.source_bounding_box),
            effective_source_bounding_box=(
                rendered_region.effective_source_bounding_box
            ),
            pixel_to_source_matrix=(rendered_region.pixel_to_source_matrix),
            pixel_rounding=rendered_region.pixel_rounding,
            page_rotation_degrees=(rendered_region.page_rotation_degrees),
            image_width=rendered_region.width_pixels,
            image_height=rendered_region.height_pixels,
        )
        return LayoutPageRenderEvidence.create(
            source_id=rendered_region.source_id,
            source_blob_id=rendered_region.source_blob_id,
            page_index=rendered_region.page_index,
            mapping=mapping,
            image_media_type=rendered_region.media_type,
            image_sha256=rendered_region.content_sha256,
            renderer_name=rendered_region.processor_name,
            renderer_version=rendered_region.processor_version,
            backend_name=rendered_region.backend_name,
            backend_version=rendered_region.backend_version,
            renderer_configuration_id=(rendered_region.configuration_digest),
        )

    def _open_document(self, payload: bytes) -> object:
        try:
            import pymupdf
        except ImportError as error:  # pragma: no cover - environment dependent
            raise PdfDependencyUnavailableError(
                "PDF region rendering requires the 'pdf' project extra"
            ) from error
        return _PyMuPdfDocument(
            backend=pymupdf,
            document=pymupdf.open(stream=payload, filetype="pdf"),
        )

    def _close_document(self, document: object) -> None:
        self._state(document).document.close()

    def _document_needs_password(self, document: object) -> bool:
        return bool(self._state(document).document.needs_pass)

    def _page_count(self, document: object) -> int:
        return int(self._state(document).document.page_count)

    def _page_dimensions(
        self,
        document: object,
        page_index: int,
    ) -> tuple[float, float]:
        page: Any = self._state(document).document.load_page(page_index)
        try:
            return (float(page.cropbox.width), float(page.cropbox.height))
        finally:
            page = None

    def _plan_geometry(
        self,
        document: object,
        selection: PageRegionSelection,
        source_bounding_box: BoundingBox,
    ) -> _PdfRegionGeometry:
        state = self._state(document)
        pymupdf = state.backend
        page: Any = state.document.load_page(selection.page_index)
        try:
            requested_display_rect = (
                pymupdf.Rect(*source_bounding_box) * page.rotation_matrix
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
            raw_label = page.get_label()
            label = (
                str(raw_label)
                if raw_label is not None and raw_label != ""
                else None
            )
            return _PdfRegionGeometry(
                width_pixels=width_pixels,
                height_pixels=height_pixels,
                effective_source_bounding_box=effective_source_box,
                pixel_to_source_matrix=pixel_to_source_matrix,
                page_rotation_degrees=int(page.rotation),
                printed_page_label=label,
                execution_state=_PyMuPdfExecutionState(
                    page_index=selection.page_index,
                    display_clip=display_clip,
                    device_x=device_x,
                    device_y=device_y,
                ),
            )
        finally:
            page = None

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
        scale = self._validated_raster_scale(
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

    def _rasterize(
        self,
        document: object,
        geometry: _PdfRegionGeometry,
    ) -> bytes:
        state = self._state(document)
        execution = cast(_PyMuPdfExecutionState, geometry.execution_state)
        pymupdf = state.backend
        page: Any = state.document.load_page(execution.page_index)
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
                clip=pymupdf.Rect(*execution.display_clip),
            )
            if (
                int(pixmap.width),
                int(pixmap.height),
                int(pixmap.x),
                int(pixmap.y),
            ) != (
                geometry.width_pixels,
                geometry.height_pixels,
                execution.device_x,
                execution.device_y,
            ):
                raise RuntimeError(
                    "PyMuPDF raster dimensions disagreed with resource "
                    "preflight"
                )
            return bytes(pixmap.tobytes("png"))
        finally:
            pixmap = None
            page = None

    def _backend_version(self, document: object) -> str:
        pymupdf = self._state(document).backend
        version = str(getattr(pymupdf, "__version__", "")).strip()
        if not version:
            raise RuntimeError("PyMuPDF does not expose its backend version")
        return version

    @staticmethod
    def _state(document: object) -> _PyMuPdfDocument:
        if not isinstance(document, _PyMuPdfDocument):
            raise TypeError("document state does not belong to PyMuPDF")
        return document

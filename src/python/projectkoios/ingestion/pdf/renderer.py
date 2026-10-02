from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import BinaryIO

from projectkoios.ingestion.models import BoundingBox, SourceDocument
from projectkoios.ingestion.pdf.models import (
    PageRegionSelection,
    PixelToSourceMatrix,
    RegionColorMode,
    RegionRenderConfiguration,
    RenderedRegion,
)


class PdfRegionRenderLimitError(ValueError):
    """Raised before raster allocation when a configured limit is exceeded."""


class PageRegionRenderer(ABC):
    """Nominal boundary for rendering explicitly selected page regions."""

    name: str
    version: str

    @abstractmethod
    def render(
        self,
        source: SourceDocument,
        content: BinaryIO,
        selections: Iterable[PageRegionSelection],
    ) -> tuple[RenderedRegion, ...]:
        """Render selections in requested order."""


@dataclass(frozen=True)
class _PdfRegionGeometry:
    """Neutral render evidence plus adapter-owned execution state."""

    width_pixels: int
    height_pixels: int
    effective_source_bounding_box: BoundingBox
    pixel_to_source_matrix: PixelToSourceMatrix
    page_rotation_degrees: int
    printed_page_label: str | None
    execution_state: object


@dataclass(frozen=True)
class _ApprovedRenderPlan:
    selection: PageRegionSelection
    source_bounding_box: BoundingBox
    geometry: _PdfRegionGeometry


class PdfRegionRenderer(PageRegionRenderer, ABC):
    """Backend-neutral PDF rendering template with bounded preflight."""

    backend_name: str

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
        # Resolve after this module has defined the limit error imported by the
        # preflight policy, avoiding a module-load cycle.
        from projectkoios.ingestion.pdf.preflight import (
            PdfRegionRenderPreflight,
        )

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
        payload = content.read()
        self._preflight.validate_source(source, payload)
        document = self._open_document(payload)
        try:
            if self._document_needs_password(document):
                raise ValueError("encrypted PDF requires a password")
            self._preflight.validate_page_indices(
                requested,
                self._page_count(document),
            )
            plans = tuple(
                self._prepare_selection(document, selection)
                for selection in self._preflight.unique_selections(requested)
            )
            resource_plans = tuple(
                self._preflight.plan(
                    plan.selection,
                    width_pixels=plan.geometry.width_pixels,
                    height_pixels=plan.geometry.height_pixels,
                )
                for plan in plans
            )
            self._preflight.validate_aggregate(resource_plans)
            backend_version = self._backend_version(document)
            rendered_by_selection: dict[
                PageRegionSelection, RenderedRegion
            ] = {}
            for plan, resources in zip(plans, resource_plans, strict=True):
                raster = self._rasterize(document, plan.geometry)
                if not isinstance(raster, bytes):
                    raise TypeError(
                        "renderer backend must return immutable bytes"
                    )
                rendered_by_selection[plan.selection] = RenderedRegion.create(
                    source=source,
                    page_index=plan.selection.page_index,
                    printed_page_label=plan.geometry.printed_page_label,
                    source_bounding_box=plan.source_bounding_box,
                    effective_source_bounding_box=(
                        plan.geometry.effective_source_bounding_box
                    ),
                    pixel_to_source_matrix=(
                        plan.geometry.pixel_to_source_matrix
                    ),
                    page_rotation_degrees=(plan.geometry.page_rotation_degrees),
                    selection_was_full_page=plan.selection.full_page,
                    configuration=self.configuration,
                    content=raster,
                    width_pixels=resources.width_pixels,
                    height_pixels=resources.height_pixels,
                    processor_name=self.name,
                    processor_version=self.version,
                    backend_name=self.backend_name,
                    backend_version=backend_version,
                )
            return tuple(
                rendered_by_selection[selection] for selection in requested
            )
        finally:
            self._close_document(document)

    def _prepare_selection(
        self,
        document: object,
        selection: PageRegionSelection,
    ) -> _ApprovedRenderPlan:
        page_width, page_height = self._page_dimensions(
            document,
            selection.page_index,
        )
        self._preflight.validate_page_dimensions(page_width, page_height)
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
        return _ApprovedRenderPlan(
            selection=selection,
            source_bounding_box=source_box,
            geometry=self._plan_geometry(document, selection, source_box),
        )

    def _validated_raster_scale(
        self,
        largest_input_dimension: float,
        *,
        input_units_per_inch: float,
    ) -> float:
        return self._preflight.validate_raster_scale(
            largest_input_dimension,
            input_units_per_inch=input_units_per_inch,
        )

    @abstractmethod
    def _open_document(self, payload: bytes) -> object:
        """Load the optional backend and return opaque document state."""

    @abstractmethod
    def _close_document(self, document: object) -> None:
        """Release opaque document state."""

    @abstractmethod
    def _document_needs_password(self, document: object) -> bool:
        """Return whether the document cannot be read without a password."""

    @abstractmethod
    def _page_count(self, document: object) -> int:
        """Return the backend page count."""

    @abstractmethod
    def _page_dimensions(
        self,
        document: object,
        page_index: int,
    ) -> tuple[float, float]:
        """Return unrotated crop-box dimensions for one page."""

    @abstractmethod
    def _plan_geometry(
        self,
        document: object,
        selection: PageRegionSelection,
        source_bounding_box: BoundingBox,
    ) -> _PdfRegionGeometry:
        """Return exact backend geometry without allocating a raster."""

    @abstractmethod
    def _rasterize(
        self,
        document: object,
        geometry: _PdfRegionGeometry,
    ) -> bytes:
        """Rasterize one already-approved geometry plan."""

    @abstractmethod
    def _backend_version(self, document: object) -> str:
        """Return the concrete backend version used by the document."""

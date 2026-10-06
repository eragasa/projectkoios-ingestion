from __future__ import annotations

import math
from collections.abc import Iterable
from itertools import islice

from projectkoios.ingestion.models import BoundingBox, SourceDocument
from projectkoios.ingestion.pdf.models import (
    PageRegionSelection,
    RegionColorMode,
    RegionRenderConfiguration,
)
from projectkoios.ingestion.pdf.preflight.plan import (
    PdfRegionRenderPreflightPlan,
)
from projectkoios.ingestion.pdf.renderer import PdfRegionRenderLimitError
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


class PdfRegionRenderPreflight:
    """Backend-neutral validation and resource policy for region rendering."""

    def __init__(self, configuration: RegionRenderConfiguration) -> None:
        if not isinstance(configuration, RegionRenderConfiguration):
            raise TypeError("configuration must be a RegionRenderConfiguration")
        self.configuration = configuration

    def prepare_request(
        self,
        source: SourceDocument,
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
        if source.media_type != "application/pdf":
            raise ValueError("PDF region rendering requires application/pdf")
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
        return requested

    @staticmethod
    def unique_selections(
        requested: tuple[PageRegionSelection, ...],
    ) -> tuple[PageRegionSelection, ...]:
        return tuple(dict.fromkeys(requested))

    @staticmethod
    def validate_source(source: SourceDocument, payload: bytes) -> None:
        digest = SHA256Fingerprinter.fingerprint(content=payload)
        if digest != source.content_hash or len(payload) != source.byte_length:
            raise ValueError("source bytes do not agree with SourceDocument")

    @staticmethod
    def validate_page_indices(
        requested: tuple[PageRegionSelection, ...],
        page_count: int,
    ) -> None:
        if (
            isinstance(page_count, bool)
            or not isinstance(page_count, int)
            or page_count < 0
        ):
            raise ValueError("page_count must be a non-negative integer")
        for selection in requested:
            if selection.page_index >= page_count:
                raise ValueError(
                    "region selection page_index is outside the PDF: "
                    f"{selection.page_index}"
                )

    @staticmethod
    def validate_page_dimensions(
        page_width: float,
        page_height: float,
    ) -> None:
        if (
            not math.isfinite(page_width)
            or not math.isfinite(page_height)
            or page_width <= 0
            or page_height <= 0
        ):
            raise ValueError("PDF page crop box must have positive area")

    @staticmethod
    def validate_bounding_box(
        bounding_box: BoundingBox,
        page_width: float,
        page_height: float,
    ) -> None:
        _, _, x1, y1 = bounding_box
        if x1 > page_width or y1 > page_height:
            raise ValueError(
                "region selection bounding_box is outside the page crop box"
            )

    def validate_raster_scale(
        self,
        largest_input_dimension: float,
        *,
        input_units_per_inch: float,
    ) -> float:
        if (
            not math.isfinite(largest_input_dimension)
            or largest_input_dimension <= 0
        ):
            raise ValueError("region selection has no finite display area")
        if not math.isfinite(input_units_per_inch) or input_units_per_inch <= 0:
            raise ValueError("input_units_per_inch must be finite and positive")
        try:
            maximum_dpi = (
                self.configuration.max_dimension_pixels
                * input_units_per_inch
                / largest_input_dimension
            )
        except OverflowError:
            maximum_dpi = math.inf
        if self.configuration.resolution_dpi > maximum_dpi:
            raise PdfRegionRenderLimitError(
                "requested DPI would exceed max_dimension_pixels before "
                "raster allocation"
            )
        try:
            return self.configuration.resolution_dpi / input_units_per_inch
        except OverflowError as error:
            raise PdfRegionRenderLimitError(
                "resolution_dpi cannot be represented for rasterization"
            ) from error

    def plan(
        self,
        selection: PageRegionSelection,
        *,
        width_pixels: int,
        height_pixels: int,
    ) -> PdfRegionRenderPreflightPlan:
        pixel_count = width_pixels * height_pixels
        channel_count = self._channel_count
        plan = PdfRegionRenderPreflightPlan(
            selection=selection,
            width_pixels=width_pixels,
            height_pixels=height_pixels,
            channel_count=channel_count,
            pixel_count=pixel_count,
            raster_byte_count=pixel_count * channel_count,
        )
        largest_dimension = max(plan.width_pixels, plan.height_pixels)
        if largest_dimension > self.configuration.max_dimension_pixels:
            raise PdfRegionRenderLimitError(
                "rendered region dimension exceeds max_dimension_pixels "
                f"({largest_dimension} > "
                f"{self.configuration.max_dimension_pixels})"
            )
        if plan.pixel_count > self.configuration.max_pixels:
            raise PdfRegionRenderLimitError(
                "rendered region pixel count exceeds max_pixels "
                f"({plan.pixel_count} > {self.configuration.max_pixels})"
            )
        if plan.raster_byte_count > self.configuration.max_raster_bytes:
            raise PdfRegionRenderLimitError(
                "rendered region raster size exceeds max_raster_bytes "
                f"({plan.raster_byte_count} > "
                f"{self.configuration.max_raster_bytes})"
            )
        return plan

    def validate_aggregate(
        self,
        plans: tuple[PdfRegionRenderPreflightPlan, ...],
    ) -> None:
        if any(plan.channel_count != self._channel_count for plan in plans):
            raise ValueError(
                "preflight plan channel count disagrees with configuration"
            )
        total_pixels = sum(plan.pixel_count for plan in plans)
        if total_pixels > self.configuration.max_total_pixels:
            raise PdfRegionRenderLimitError(
                "render request pixel count exceeds max_total_pixels "
                f"({total_pixels} > "
                f"{self.configuration.max_total_pixels})"
            )
        total_raster_bytes = sum(plan.raster_byte_count for plan in plans)
        if total_raster_bytes > self.configuration.max_total_raster_bytes:
            raise PdfRegionRenderLimitError(
                "render request raster size exceeds max_total_raster_bytes "
                f"({total_raster_bytes} > "
                f"{self.configuration.max_total_raster_bytes})"
            )

    @property
    def _channel_count(self) -> int:
        return 3 if self.configuration.color_mode is RegionColorMode.RGB else 1

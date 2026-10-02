from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.pdf.models import PageRegionSelection


@dataclass(frozen=True)
class PdfRegionRenderPreflightPlan:
    """An approved backend-neutral allocation for one unique selection."""

    selection: PageRegionSelection
    width_pixels: int
    height_pixels: int
    channel_count: int
    pixel_count: int
    raster_byte_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.selection, PageRegionSelection):
            raise TypeError("selection must be a PageRegionSelection")
        for name, value in (
            ("width_pixels", self.width_pixels),
            ("height_pixels", self.height_pixels),
            ("channel_count", self.channel_count),
            ("pixel_count", self.pixel_count),
            ("raster_byte_count", self.raster_byte_count),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer")
        expected_pixels = self.width_pixels * self.height_pixels
        if self.pixel_count != expected_pixels:
            raise ValueError("pixel_count does not match raster dimensions")
        if self.raster_byte_count != expected_pixels * self.channel_count:
            raise ValueError(
                "raster_byte_count does not match pixels and channels"
            )

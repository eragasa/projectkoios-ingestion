"""Private image/source geometry helpers for OCR evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectkoios.ingestion.models import (
    BoundingBox,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.ocr.page_image import OCRPageImage
from projectkoios.ingestion.ocr import _primitives as primitives


def _pixel_box(image: OCRPageImage, box: BoundingBox) -> BoundingBox:

    normalized = primitives._finite_box(box, "pixel_bounding_box")
    x0, y0, x1, y1 = normalized
    region = image.rendered_region
    if x0 < 0.0 or y0 < 0.0:
        raise ValueError("OCR pixel box coordinates must be non-negative")
    if x1 > region.width_pixels or y1 > region.height_pixels:
        raise ValueError("OCR pixel box lies outside its image")
    return normalized


def _map_pixel_box(image: OCRPageImage, box: BoundingBox) -> BoundingBox:

    a, b, c, d, e, f = image.rendered_region.pixel_to_source_matrix
    x0, y0, x1, y1 = box
    corners = (
        (x0 * a + y0 * c + e, x0 * b + y0 * d + f),
        (x1 * a + y0 * c + e, x1 * b + y0 * d + f),
        (x0 * a + y1 * c + e, x0 * b + y1 * d + f),
        (x1 * a + y1 * c + e, x1 * b + y1 * d + f),
    )
    xs = tuple(point[0] for point in corners)
    ys = tuple(point[1] for point in corners)
    return primitives._finite_box(
        (min(xs), min(ys), max(xs), max(ys)),
        "source_bounding_box",
    )

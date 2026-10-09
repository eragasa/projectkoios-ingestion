"""Shared COCO render-space overlap derivation."""

from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


def coco_layout_intersection_over_union(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    """Return exact raster-box intersection over union."""
    first_box = LayoutValueValidation.require_box("first", first)
    second_box = LayoutValueValidation.require_box("second", second)
    intersection_width = max(
        0.0, min(first_box[2], second_box[2]) - max(first_box[0], second_box[0])
    )
    intersection_height = max(
        0.0, min(first_box[3], second_box[3]) - max(first_box[1], second_box[1])
    )
    intersection = intersection_width * intersection_height
    first_area = (first_box[2] - first_box[0]) * (first_box[3] - first_box[1])
    second_area = (second_box[2] - second_box[0]) * (
        second_box[3] - second_box[1]
    )
    return intersection / (first_area + second_area - intersection)

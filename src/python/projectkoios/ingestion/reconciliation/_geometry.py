"""Private text normalization and geometry comparison helpers."""

from __future__ import annotations

import math
import unicodedata
from typing import TYPE_CHECKING

from projectkoios.ingestion.models import (
    BoundingBox,
    SourceSpan,
)
from projectkoios.ingestion.reconciliation._limits import (
    _MAX_TEXT_CHARACTERS_PER_ITEM,
)
from projectkoios.ingestion.reconciliation.limit_error import (
    OCRReconciliationLimitError,
)

if TYPE_CHECKING:
    pass


def _normalized_text(value: str) -> str:

    normalized = " ".join(
        unicodedata.normalize("NFKC", value).casefold().split()
    )
    if len(normalized) > _MAX_TEXT_CHARACTERS_PER_ITEM:
        raise OCRReconciliationLimitError(
            "normalized text exceeds the implementation maximum"
        )
    return normalized


def _spans_bounding_box(
    source_spans: tuple[SourceSpan, ...],
) -> BoundingBox | None:
    boxes = tuple(
        span.bounding_box
        for span in source_spans
        if span.bounding_box is not None
    )
    if len(boxes) != len(source_spans) or not boxes:
        return None
    return _validated_box(
        (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
    )


def _geometry_overlap(
    first: BoundingBox | None, second: BoundingBox | None
) -> float | None:
    if first is None or second is None:
        return None
    x0 = max(first[0], second[0])
    y0 = max(first[1], second[1])
    x1 = min(first[2], second[2])
    y1 = min(first[3], second[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    intersection = (x1 - x0) * (y1 - y0)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    overlap = intersection / min(first_area, second_area)
    return _unit_float("geometry overlap", min(1.0, max(0.0, overlap)))


def _validated_box(value: BoundingBox) -> BoundingBox:
    if not isinstance(value, tuple) or len(value) != 4:
        raise TypeError("bounding box must be an immutable four-tuple")
    coordinates: list[float] = []
    for coordinate in value:
        if isinstance(coordinate, bool) or not isinstance(
            coordinate, int | float
        ):
            raise ValueError("bounding box coordinates must be finite")
        normalized = float(coordinate)
        if not math.isfinite(normalized):
            raise ValueError("bounding box coordinates must be finite")
        coordinates.append(0.0 if normalized == 0.0 else normalized)
    x0, y0, x1, y1 = coordinates
    if x1 <= x0 or y1 <= y0:
        raise ValueError("bounding box must have positive area")
    return (x0, y0, x1, y1)


def _unit_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a finite number")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{name} must be between zero and one")
    return 0.0 if normalized == 0.0 else normalized

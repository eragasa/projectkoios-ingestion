"""Normalized source geometry for reading evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)


@dataclass(frozen=True, slots=True)
class ReadingBoundingBox:
    """One finite normalized positive-area source-space rectangle."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        values = (self.x0, self.y0, self.x1, self.y1)
        if any(
            type(value) is not float or not math.isfinite(value)
            for value in values
        ):
            raise ReadingEvidenceError(
                "bounding-box coordinates must be finite floats"
            )
        if any(value < 0.0 or value > 1.0 for value in values):
            raise ReadingEvidenceError(
                "bounding-box coordinates must be normalized"
            )
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ReadingEvidenceError(
                "bounding-box coordinates must have positive area"
            )

    def identity_material(self) -> list[float]:
        """Return ephemeral canonical coordinate material."""
        return [self.x0, self.y0, self.x1, self.y1]

"""OCRConfidence OCR domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.validation import value as primitives


@dataclass(frozen=True)
class OCRConfidence(AbstractImmutableDataObject):
    """An optional adapter score with explicit method and scale semantics."""

    value: float
    method: str
    method_version: str
    scale: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", primitives._confidence_value(self.value)
        )
        for name, value in (
            ("method", self.method),
            ("method_version", self.method_version),
            ("scale", self.scale),
        ):
            primitives._hard_bounded_string(name, value, nonempty=True)

    def identity_parts(self) -> tuple[object, ...]:
        return (self.value, self.method, self.method_version, self.scale)

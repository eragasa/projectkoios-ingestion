"""Figure-relevance confidence record."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.figures.relevance.validation import (
    value as value_validation,
)


@dataclass(frozen=True)
class FigureRelevanceConfidence:
    """Optional confidence in the proposal, distinct from relevance score."""

    value: float
    method: str
    method_version: str
    scale: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            value_validation._unit_float("confidence", self.value),
        )
        value_validation._identity_fields(
            self.method, self.method_version, self.scale
        )

    def identity_parts(self) -> tuple[object, ...]:
        return (self.value, self.method, self.method_version, self.scale)

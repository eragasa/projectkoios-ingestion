"""Figure-relevance processor identity record."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.figures.relevance.identity.resource.model import (
    FigureRelevanceResourceIdentity,
)
from projectkoios.ingestion.figures.relevance.limits.definition import (
    _MAX_RESOURCES,
)
from projectkoios.ingestion.figures.relevance.limits.error import (
    FigureRelevanceLimitError,
)
from projectkoios.ingestion.figures.relevance.validation import (
    value as value_validation,
)
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True)
class FigureRelevanceProcessorIdentity:
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    resources: tuple[FigureRelevanceResourceIdentity, ...] = ()

    def __post_init__(self) -> None:
        value_validation._identity_fields(
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        value_validation._require_tuple("resources", self.resources)
        if len(self.resources) > _MAX_RESOURCES:
            raise FigureRelevanceLimitError("too many resource identities")
        if any(
            not isinstance(item, FigureRelevanceResourceIdentity)
            for item in self.resources
        ):
            raise TypeError("resources contain an unsupported value")
        names = tuple(item.resource_name for item in self.resources)
        if len(set(names)) != len(names):
            raise ValueError("resource names must be unique")
        if names != tuple(sorted(names)):
            raise ValueError("resource identities must be ordered by name")

    @property
    def identity_digest(self) -> str:
        return stable_id("figure-relevance-processor", self.identity_parts())

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
            tuple(item.identity_parts() for item in self.resources),
        )

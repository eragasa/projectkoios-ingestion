"""Figure-relevance resource identity record."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.figures.relevance.identity.resource.kind import (
    FigureRelevanceResourceIdentityKind,
)
from projectkoios.ingestion.figures.relevance.validation import (
    value as value_validation,
)


@dataclass(frozen=True)
class FigureRelevanceResourceIdentity:
    resource_name: str
    identity_kind: FigureRelevanceResourceIdentityKind
    resource_identity: str

    def __post_init__(self) -> None:
        value_validation._bounded_string(
            "resource name", self.resource_name, nonempty=True
        )
        if not isinstance(
            self.identity_kind, FigureRelevanceResourceIdentityKind
        ):
            raise TypeError(
                "unsupported figure-relevance resource identity kind"
            )
        value_validation._bounded_string(
            "resource identity", self.resource_identity, nonempty=True
        )
        if self.identity_kind is FigureRelevanceResourceIdentityKind.SHA256:
            value_validation._sha256(
                "resource identity", self.resource_identity
            )

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.resource_name,
            self.identity_kind.value,
            self.resource_identity,
        )

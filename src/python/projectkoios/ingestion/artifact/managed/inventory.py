"""Bounded managed artifact reference inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.artifact.managed.limits.definition import (
    MANAGED_ARTIFACT_LIMITS,
)
from projectkoios.ingestion.artifact.managed.limits.error import (
    ManagedArtifactLimitError,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)


@dataclass(frozen=True, slots=True, init=False)
class ManagedArtifactReferenceInventory:
    """Own one sorted, unique, bounded managed-reference collection."""

    _references: tuple[ManagedArtifactReference, ...] = field(repr=True)

    def __init__(self, *references: ManagedArtifactReference) -> None:
        values = tuple(references)
        if len(values) > MANAGED_ARTIFACT_LIMITS.maximum_references:
            raise ManagedArtifactLimitError(
                "managed artifact reference count exceeds its limit"
            )
        if any(type(value) is not ManagedArtifactReference for value in values):
            raise TypeError(
                "managed artifact inventory requires exact references"
            )
        identities = tuple(value.artifact_id for value in values)
        if identities != tuple(sorted(identities)):
            raise ValueError("managed artifact references must be sorted")
        if len(identities) != len(set(identities)):
            raise ValueError("managed artifact references must be unique")
        if (
            sum(value.byte_length for value in values)
            > MANAGED_ARTIFACT_LIMITS.maximum_aggregate_bytes
        ):
            raise ManagedArtifactLimitError(
                "managed artifact aggregate bytes exceed their limit"
            )
        object.__setattr__(self, "_references", values)

    def __bool__(self) -> bool:
        return bool(self._references)

    def __iter__(self) -> Iterator[ManagedArtifactReference]:
        return iter(self._references)

    def __len__(self) -> int:
        return len(self._references)

    @property
    def aggregate_byte_length(self) -> int:
        """Return the exact aggregate referenced byte count."""
        return sum(value.byte_length for value in self._references)

    def require(self, artifact_id: str) -> ManagedArtifactReference:
        """Return the exact referenced artifact or fail closed."""
        for reference in self._references:
            if reference.artifact_id == artifact_id:
                return reference
        raise ValueError("managed artifact reference is absent")

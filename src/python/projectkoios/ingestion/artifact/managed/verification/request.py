"""Immutable requests for exact managed-artifact verification."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.artifact.managed.limits.definition import (
    MANAGED_ARTIFACT_LIMITS,
)
from projectkoios.ingestion.artifact.managed.limits.error import (
    ManagedArtifactLimitError,
)
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class ManagedArtifactVerificationRequest(DataObjectActionRequest):
    """Bind exact references, provider role, authority, and streaming bounds."""

    references: ManagedArtifactReferenceInventory
    provider_implementation_id: str
    authority_id: str
    maximum_artifact_bytes: int
    maximum_aggregate_bytes: int
    stream_chunk_bytes: int
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.references) is not ManagedArtifactReferenceInventory:
            raise TypeError("references must be a managed artifact inventory")
        provider_id = MANAGED_ARTIFACT_LIMITS.require_identity_text(
            self.provider_implementation_id, "provider_implementation_id"
        )
        authority_id = MANAGED_ARTIFACT_LIMITS.require_identity_text(
            self.authority_id, "authority_id"
        )
        bounds = (
            (
                self.maximum_artifact_bytes,
                MANAGED_ARTIFACT_LIMITS.maximum_artifact_bytes,
                "maximum_artifact_bytes",
            ),
            (
                self.maximum_aggregate_bytes,
                MANAGED_ARTIFACT_LIMITS.maximum_aggregate_bytes,
                "maximum_aggregate_bytes",
            ),
            (
                self.stream_chunk_bytes,
                MANAGED_ARTIFACT_LIMITS.maximum_stream_chunk_bytes,
                "stream_chunk_bytes",
            ),
        )
        for value, maximum, name in bounds:
            if type(value) is not int or not 1 <= value <= maximum:
                raise ManagedArtifactLimitError(f"{name} is outside its bounds")
        if any(
            reference.byte_length > self.maximum_artifact_bytes
            for reference in self.references
        ):
            raise ManagedArtifactLimitError(
                "a referenced artifact exceeds the requested per-artifact bound"
            )
        if self.references.aggregate_byte_length > self.maximum_aggregate_bytes:
            raise ManagedArtifactLimitError(
                "referenced artifacts exceed the requested aggregate bound"
            )
        object.__setattr__(self, "provider_implementation_id", provider_id)
        object.__setattr__(self, "authority_id", authority_id)
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                "managed-artifact-verification-request",
                self.references.inventory_id,
                provider_id,
                authority_id,
                self.maximum_artifact_bytes,
                self.maximum_aggregate_bytes,
                self.stream_chunk_bytes,
            ),
        )

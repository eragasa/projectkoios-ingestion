"""Exact locator-free managed artifact references."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.artifact.managed.limits.definition import (
    MANAGED_ARTIFACT_LIMITS,
)
from projectkoios.ingestion.artifact.managed.limits.error import (
    ManagedArtifactLimitError,
)
from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class ManagedArtifactReference(AbstractImmutableDataObject):
    """Identify exact externally managed bytes without locating them."""

    CONTRACT_NAME: ClassVar[str] = "managed-artifact-reference"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    sha256: SHA256Hash
    byte_length: int
    media_type: ManagedArtifactMediaType
    artifact_id: str = field(init=False)

    def __post_init__(self) -> None:
        digest = MANAGED_ARTIFACT_LIMITS.require_sha256(self.sha256, "sha256")
        length = MANAGED_ARTIFACT_LIMITS.require_byte_length(
            self.byte_length, "byte_length"
        )
        if not isinstance(self.media_type, ManagedArtifactMediaType):
            raise TypeError("media_type must be ManagedArtifactMediaType")
        identity_input = CanonicalJsonSerializer.serialize_bytes(
            {
                "contract_name": self.CONTRACT_NAME,
                "contract_version": self.CONTRACT_VERSION,
                "sha256": digest,
                "byte_length": length,
                "media_type": self.media_type,
            }
        )
        if (
            len(identity_input)
            > MANAGED_ARTIFACT_LIMITS.maximum_identity_input_bytes
        ):
            raise ManagedArtifactLimitError(
                "managed artifact identity input exceeds its limit"
            )
        object.__setattr__(self, "sha256", digest)
        object.__setattr__(
            self,
            "artifact_id",
            "managed-artifact:sha256:"
            + SHA256Fingerprinter.fingerprint(content=identity_input),
        )

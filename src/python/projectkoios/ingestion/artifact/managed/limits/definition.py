"""Immutable resource ceilings for managed artifact references."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.artifact.managed.limits.error import (
    ManagedArtifactLimitError,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class ManagedArtifactLimits:
    """Own fixed managed-reference and aggregate ceilings."""

    maximum_identity_characters: int = field(default=512, init=False)
    maximum_references: int = field(default=4_096, init=False)
    maximum_verifications: int = field(default=4_096, init=False)
    maximum_artifact_bytes: int = field(default=4_000_000_000, init=False)
    maximum_aggregate_bytes: int = field(default=64_000_000_000, init=False)
    maximum_stream_chunk_bytes: int = field(default=8_388_608, init=False)
    maximum_media_signature_bytes: int = field(default=4_096, init=False)
    maximum_identity_input_bytes: int = field(default=16_384, init=False)

    def require_identity_text(self, value: object, name: str) -> str:
        """Return one bounded nonempty identity component."""
        if type(value) is not str or not value:
            raise ValueError(f"{name} must be a non-empty string")
        try:
            encoded = value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise ValueError(f"{name} must be valid UTF-8") from error
        if len(encoded) > self.maximum_identity_characters:
            raise ManagedArtifactLimitError(f"{name} exceeds its limit")
        return value

    def require_sha256(self, value: object, name: str) -> SHA256Hash:
        """Return one canonical SHA-256 value."""
        if not SHA256Hash.is_canonical(value):
            raise ValueError(f"{name} must be a canonical SHA-256 digest")
        return SHA256Hash(str(value))

    def require_byte_length(self, value: object, name: str) -> int:
        """Return one positive bounded built-in byte count."""
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be a positive built-in integer")
        if value > self.maximum_artifact_bytes:
            raise ManagedArtifactLimitError(f"{name} exceeds its limit")
        return value


MANAGED_ARTIFACT_LIMITS = ManagedArtifactLimits()

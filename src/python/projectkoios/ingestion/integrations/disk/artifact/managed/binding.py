"""Explicit disk locator bindings for locator-free managed artifacts."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from projectkoios.ingestion.artifact.managed.limits.definition import (
    MANAGED_ARTIFACT_LIMITS,
)
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class DiskManagedArtifactBinding(AbstractImmutableDataObject):
    """Bind one artifact identity to one canonical root-relative disk path."""

    artifact_id: str
    relative_path: str

    def __post_init__(self) -> None:
        artifact_id = MANAGED_ARTIFACT_LIMITS.require_identity_text(
            self.artifact_id, "artifact_id"
        )
        artifact_prefix = "managed-artifact:sha256:"
        if not artifact_id.startswith(
            artifact_prefix
        ) or not SHA256Hash.is_canonical(
            artifact_id.removeprefix(artifact_prefix)
        ):
            raise ValueError("artifact_id must identify a managed artifact")
        if (
            type(self.relative_path) is not str
            or not self.relative_path
            or "\x00" in self.relative_path
            or "\\" in self.relative_path
        ):
            raise ValueError("relative_path must be a non-empty portable path")
        encoded = self.relative_path.encode("utf-8", errors="strict")
        if len(encoded) > 4_096:
            raise ValueError("relative_path exceeds its limit")
        path = PurePosixPath(self.relative_path)
        if (
            path.is_absolute()
            or str(path) != self.relative_path
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError(
                "relative_path must be canonical and root-relative"
            )
        object.__setattr__(self, "artifact_id", artifact_id)


@dataclass(frozen=True, slots=True, init=False)
class DiskManagedArtifactBindingInventory:
    """Own sorted unique artifact-to-path bindings for one disk provider."""

    _bindings: tuple[DiskManagedArtifactBinding, ...] = field(repr=True)

    def __init__(self, *bindings: DiskManagedArtifactBinding) -> None:
        values = tuple(bindings)
        if len(values) > MANAGED_ARTIFACT_LIMITS.maximum_references:
            raise ValueError(
                "disk managed artifact binding count exceeds its limit"
            )
        if any(
            type(value) is not DiskManagedArtifactBinding for value in values
        ):
            raise TypeError("disk binding inventory requires exact bindings")
        artifact_ids = tuple(value.artifact_id for value in values)
        relative_paths = tuple(value.relative_path for value in values)
        if artifact_ids != tuple(sorted(artifact_ids)):
            raise ValueError("disk managed artifact bindings must be sorted")
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("disk managed artifact identities must be unique")
        if len(relative_paths) != len(set(relative_paths)):
            raise ValueError("disk managed artifact paths must be unique")
        object.__setattr__(self, "_bindings", values)

    def __iter__(self) -> Iterator[DiskManagedArtifactBinding]:
        return iter(self._bindings)

    def __len__(self) -> int:
        return len(self._bindings)

    def require(self, artifact_id: str) -> DiskManagedArtifactBinding:
        """Return the exact configured binding or fail closed."""
        for binding in self._bindings:
            if binding.artifact_id == artifact_id:
                return binding
        raise ValueError("disk managed artifact binding is absent")

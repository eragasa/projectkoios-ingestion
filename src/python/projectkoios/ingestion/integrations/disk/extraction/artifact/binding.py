"""Explicit bindings for private extraction artifacts on disk."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id

_MAXIMUM_BINDINGS = 100_000
_MAXIMUM_TEXT_BYTES = 4_096


@dataclass(frozen=True, slots=True)
class DiskExtractionArtifactBinding(AbstractImmutableDataObject):
    """Bind one opaque extraction-artifact reference to a relative path."""

    artifact_reference: str
    relative_path: str

    def __post_init__(self) -> None:
        if (
            type(self.artifact_reference) is not str
            or not self.artifact_reference
            or len(self.artifact_reference.encode("utf-8", errors="strict"))
            > _MAXIMUM_TEXT_BYTES
        ):
            raise ValueError("artifact_reference is invalid")
        if (
            type(self.relative_path) is not str
            or not self.relative_path
            or "\x00" in self.relative_path
            or "\\" in self.relative_path
            or len(self.relative_path.encode("utf-8", errors="strict"))
            > _MAXIMUM_TEXT_BYTES
        ):
            raise ValueError("relative_path is invalid")
        path = PurePosixPath(self.relative_path)
        if (
            path.is_absolute()
            or str(path) != self.relative_path
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError(
                "relative_path must be canonical and root-relative"
            )


@dataclass(frozen=True, slots=True, init=False)
class DiskExtractionArtifactBindingInventory:
    """Own sorted one-to-one disk extraction-artifact bindings."""

    _bindings: tuple[DiskExtractionArtifactBinding, ...] = field(repr=True)
    binding_inventory_id: str = field(init=False)

    def __init__(self, *bindings: DiskExtractionArtifactBinding) -> None:
        values = tuple(bindings)
        if len(values) > _MAXIMUM_BINDINGS:
            raise ValueError("disk extraction binding count exceeds its limit")
        if any(
            type(value) is not DiskExtractionArtifactBinding for value in values
        ):
            raise TypeError("disk extraction bindings have invalid types")
        references = tuple(value.artifact_reference for value in values)
        paths = tuple(value.relative_path for value in values)
        if references != tuple(sorted(references)):
            raise ValueError("disk extraction bindings must be sorted")
        if len(references) != len(set(references)):
            raise ValueError("disk extraction references must be unique")
        if len(paths) != len(set(paths)):
            raise ValueError("disk extraction paths must be unique")
        digest = hashlib.sha256()
        for value in values:
            for component in (
                value.artifact_reference,
                value.relative_path,
            ):
                encoded = component.encode("utf-8", errors="strict")
                digest.update(len(encoded).to_bytes(8, byteorder="big"))
                digest.update(encoded)
        object.__setattr__(self, "_bindings", values)
        object.__setattr__(
            self,
            "binding_inventory_id",
            stable_id(
                "disk-extraction-artifact-binding-inventory",
                "1.0",
                len(values),
                digest.hexdigest(),
            ),
        )

    def __iter__(self) -> Iterator[DiskExtractionArtifactBinding]:
        return iter(self._bindings)

    def __len__(self) -> int:
        return len(self._bindings)

    def require(self, artifact_reference: str) -> DiskExtractionArtifactBinding:
        """Return one exact binding or fail closed."""
        for binding in self._bindings:
            if binding.artifact_reference == artifact_reference:
                return binding
        raise ValueError("disk extraction artifact binding is absent")

"""Symlink-safe bounded disk provider for managed-artifact bytes."""

from __future__ import annotations

import errno
import os
import stat
from collections.abc import Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path, PurePosixPath

from projectkoios.ingestion.artifact.managed.limits.definition import (
    MANAGED_ARTIFACT_LIMITS,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.artifact.managed.verification.error import (
    ManagedArtifactVerificationError,
)
from projectkoios.ingestion.artifact.managed.verification.provider import (
    ManagedArtifactByteProvider,
)
from projectkoios.ingestion.integrations.disk.artifact.managed.binding import (
    DiskManagedArtifactBindingInventory,
)


class DiskManagedArtifactByteProvider(ManagedArtifactByteProvider):
    """Resolve configured identities beneath one immutable disk root."""

    __slots__ = ("_authority_id", "bindings", "root")

    IMPLEMENTATION_ID = "disk-managed-artifact-byte-provider:1.0"

    def __init__(
        self,
        *,
        root: Path,
        bindings: DiskManagedArtifactBindingInventory,
        authority_id: str,
    ) -> None:
        if not isinstance(root, Path):
            raise TypeError("root must be a Path")
        expanded_root = root.expanduser()
        if len(os.fsencode(expanded_root)) > 4_096:
            raise ValueError("disk managed artifact root exceeds its limit")
        try:
            if expanded_root.is_symlink():
                raise ValueError(
                    "disk managed artifact root cannot be a symlink"
                )
            resolved_root = expanded_root.resolve(strict=True)
            if not resolved_root.is_dir():
                raise ValueError(
                    "disk managed artifact root must be a directory"
                )
        except OSError:
            raise ValueError(
                "disk managed artifact root is unavailable"
            ) from None
        if type(bindings) is not DiskManagedArtifactBindingInventory:
            raise TypeError("bindings must be a disk binding inventory")
        validated_authority = MANAGED_ARTIFACT_LIMITS.require_identity_text(
            authority_id, "authority_id"
        )
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            raise RuntimeError(
                "secure descriptor-relative disk access is unavailable"
            )
        self.root = resolved_root
        self.bindings = bindings
        self._authority_id = validated_authority

    @property
    def implementation_id(self) -> str:
        """Identify the exact disk-provider implementation contract."""
        return self.IMPLEMENTATION_ID

    def open_chunks(
        self,
        *,
        reference: ManagedArtifactReference,
        authority_id: str,
        maximum_bytes: int,
        chunk_bytes: int,
    ) -> AbstractContextManager[Iterator[bytes]]:
        """Open one bound file for safe bounded chunk iteration."""
        if type(reference) is not ManagedArtifactReference:
            raise TypeError("reference must be a ManagedArtifactReference")
        if authority_id != self._authority_id:
            raise ManagedArtifactVerificationError(
                code="authority_differs",
                message="disk managed artifact authority differs",
            )
        if (
            type(maximum_bytes) is not int
            or not 1
            <= maximum_bytes
            <= MANAGED_ARTIFACT_LIMITS.maximum_artifact_bytes
        ):
            raise ValueError("maximum_bytes is outside its bounds")
        if (
            type(chunk_bytes) is not int
            or not 1
            <= chunk_bytes
            <= MANAGED_ARTIFACT_LIMITS.maximum_stream_chunk_bytes
        ):
            raise ValueError("chunk_bytes is outside its bounds")
        try:
            binding = self.bindings.require(reference.artifact_id)
        except ValueError as error:
            raise ManagedArtifactVerificationError(
                code="artifact_binding_missing",
                message="managed artifact has no configured disk binding",
            ) from error
        return self._open_file_chunks(
            relative_path=binding.relative_path,
            maximum_bytes=maximum_bytes,
            chunk_bytes=chunk_bytes,
        )

    @contextmanager
    def _open_file_chunks(
        self,
        *,
        relative_path: str,
        maximum_bytes: int,
        chunk_bytes: int,
    ) -> Iterator[Iterator[bytes]]:
        chunks = self._read_file_chunks(
            relative_path=relative_path,
            maximum_bytes=maximum_bytes,
            chunk_bytes=chunk_bytes,
        )
        try:
            yield chunks
        finally:
            chunks.close()

    def _read_file_chunks(
        self,
        *,
        relative_path: str,
        maximum_bytes: int,
        chunk_bytes: int,
    ) -> Generator[bytes]:
        descriptors: list[int] = []
        try:
            directory_flags = (
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            )
            file_flags = (
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
            )
            descriptors.append(os.open(self.root.anchor, directory_flags))
            for root_part in self.root.parts[1:]:
                descriptors.append(
                    os.open(
                        root_part,
                        directory_flags,
                        dir_fd=descriptors[-1],
                    )
                )
            parts = PurePosixPath(relative_path).parts
            for part in parts[:-1]:
                descriptors.append(
                    os.open(part, directory_flags, dir_fd=descriptors[-1])
                )
            descriptors.append(
                os.open(parts[-1], file_flags, dir_fd=descriptors[-1])
            )
            file_descriptor = descriptors[-1]
            file_status = os.fstat(file_descriptor)
            if not stat.S_ISREG(file_status.st_mode):
                raise ManagedArtifactVerificationError(
                    code="unsafe_artifact_path",
                    message="disk managed artifact is not a regular file",
                )
            if file_status.st_size > maximum_bytes:
                raise ManagedArtifactVerificationError(
                    code="artifact_byte_limit_exceeded",
                    message=(
                        "disk managed artifact exceeds its exact byte bound"
                    ),
                )
            observed_bytes = 0
            while True:
                chunk = os.read(file_descriptor, chunk_bytes)
                if not chunk:
                    break
                observed_bytes += len(chunk)
                if observed_bytes > maximum_bytes:
                    raise ManagedArtifactVerificationError(
                        code="artifact_byte_limit_exceeded",
                        message=(
                            "disk managed artifact exceeded its byte bound"
                        ),
                    )
                yield chunk
        except ManagedArtifactVerificationError:
            raise
        except OSError as error:
            raise _disk_provider_error(error) from None
        finally:
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def _disk_provider_error(error: OSError) -> ManagedArtifactVerificationError:
    if error.errno == errno.ENOENT:
        return ManagedArtifactVerificationError(
            code="artifact_unavailable",
            message="disk managed artifact is unavailable",
        )
    if error.errno in {errno.ELOOP, errno.ENOTDIR}:
        return ManagedArtifactVerificationError(
            code="unsafe_artifact_path",
            message="disk managed artifact path is unsafe",
        )
    return ManagedArtifactVerificationError(
        code="provider_read_failed",
        message="disk managed artifact provider could not read the artifact",
    )

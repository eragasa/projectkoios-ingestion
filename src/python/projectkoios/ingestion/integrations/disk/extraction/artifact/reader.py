"""Symlink-safe bounded reader for private extraction artifacts on disk."""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path, PurePosixPath

from projectkoios.ingestion.integrations.disk.extraction.artifact.binding import (  # noqa: E501
    DiskExtractionArtifactBindingInventory,
)
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.artifact.validation.reader.base import (  # noqa: E501
    ExtractionArtifactReader,
)
from projectkoios.ingestion.storage.extraction.artifact.validation.reader.error import (  # noqa: E501
    ExtractionArtifactReaderError,
)

_MAXIMUM_TEXT_BYTES = 4_096
_READ_CHUNK_BYTES = 1_048_576


class DiskExtractionArtifactReader(ExtractionArtifactReader):
    """Resolve configured artifact references beneath one immutable root."""

    __slots__ = (
        "_authority_id",
        "_root_device",
        "_root_inode",
        "bindings",
        "root",
    )

    IMPLEMENTATION_ID = "disk-extraction-artifact-reader:1.0"

    def __init__(
        self,
        *,
        root: Path,
        bindings: DiskExtractionArtifactBindingInventory,
        authority_id: str,
    ) -> None:
        if not isinstance(root, Path):
            raise TypeError("root must be a Path")
        expanded = root.expanduser()
        if len(os.fsencode(expanded)) > _MAXIMUM_TEXT_BYTES:
            raise ValueError("disk extraction artifact root exceeds its limit")
        try:
            if expanded.is_symlink():
                raise ValueError(
                    "disk extraction artifact root cannot be a symlink"
                )
            resolved = expanded.resolve(strict=True)
            if not resolved.is_dir():
                raise ValueError(
                    "disk extraction artifact root must be a directory"
                )
        except OSError:
            raise ValueError(
                "disk extraction artifact root is unavailable"
            ) from None
        if type(bindings) is not DiskExtractionArtifactBindingInventory:
            raise TypeError("bindings have an unsupported type")
        if (
            type(authority_id) is not str
            or not authority_id
            or len(authority_id.encode("utf-8", errors="strict"))
            > _MAXIMUM_TEXT_BYTES
        ):
            raise ValueError("authority_id is invalid")
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            raise RuntimeError(
                "secure descriptor-relative disk access is unavailable"
            )
        root_status = resolved.stat(follow_symlinks=False)
        self.root = resolved
        self.bindings = bindings
        self._authority_id = authority_id
        self._root_device = root_status.st_dev
        self._root_inode = root_status.st_ino

    @property
    def implementation_id(self) -> str:
        """Return the exact reader implementation identity."""
        return self.IMPLEMENTATION_ID

    def read(
        self,
        *,
        artifact_reference: str,
        authority_id: str,
        maximum_bytes: int,
    ) -> bytes:
        """Read one explicitly bound regular file under an exact byte bound."""
        if authority_id != self._authority_id:
            raise ExtractionArtifactReaderError(
                code="artifact_read_authority_required",
                disposition=ExtractionActionDisposition.AUTHORITY_REQUIRED,
                message="disk extraction artifact authority differs",
            )
        if (
            type(maximum_bytes) is not int
            or not 1 <= maximum_bytes <= 512_000_000
        ):
            raise ValueError("maximum_bytes is outside its bounds")
        try:
            binding = self.bindings.require(artifact_reference)
        except ValueError as error:
            raise ExtractionArtifactReaderError(
                code="artifact_binding_missing",
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                message="extraction artifact has no configured disk binding",
            ) from error
        return self._read_file(
            relative_path=binding.relative_path,
            maximum_bytes=maximum_bytes,
        )

    def _read_file(self, *, relative_path: str, maximum_bytes: int) -> bytes:
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
            root_status = os.fstat(descriptors[-1])
            if (
                root_status.st_dev != self._root_device
                or root_status.st_ino != self._root_inode
            ):
                raise ExtractionArtifactReaderError(
                    code="unsafe_artifact_root",
                    disposition=ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                    message="disk extraction artifact root identity changed",
                )
            parts = PurePosixPath(relative_path).parts
            for part in parts[:-1]:
                descriptors.append(
                    os.open(part, directory_flags, dir_fd=descriptors[-1])
                )
            descriptors.append(
                os.open(parts[-1], file_flags, dir_fd=descriptors[-1])
            )
            descriptor = descriptors[-1]
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise ExtractionArtifactReaderError(
                    code="unsafe_artifact_path",
                    disposition=ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                    message="disk extraction artifact is not a regular file",
                )
            if before.st_size > maximum_bytes:
                raise ExtractionArtifactReaderError(
                    code="artifact_byte_limit_exceeded",
                    disposition=ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                    message="disk extraction artifact exceeds its byte bound",
                )
            chunks: list[bytes] = []
            observed = 0
            while True:
                chunk = os.read(descriptor, _READ_CHUNK_BYTES)
                if not chunk:
                    break
                observed += len(chunk)
                if observed > maximum_bytes:
                    raise ExtractionArtifactReaderError(
                        code="artifact_byte_limit_exceeded",
                        disposition=(
                            ExtractionActionDisposition.STOP_INVALID_EVIDENCE
                        ),
                        message=(
                            "disk extraction artifact exceeded its byte bound"
                        ),
                    )
                chunks.append(chunk)
            after = os.fstat(descriptor)
            if (
                observed != before.st_size
                or after.st_size != before.st_size
                or after.st_mtime_ns != before.st_mtime_ns
                or after.st_ctime_ns != before.st_ctime_ns
            ):
                raise ExtractionArtifactReaderError(
                    code="artifact_changed_during_read",
                    disposition=(
                        ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                    ),
                    message="disk extraction artifact changed during reading",
                )
            return b"".join(chunks)
        except ExtractionArtifactReaderError:
            raise
        except OSError as error:
            raise _disk_reader_error(error) from None
        finally:
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def _disk_reader_error(error: OSError) -> ExtractionArtifactReaderError:
    if error.errno == errno.ENOENT:
        return ExtractionArtifactReaderError(
            code="artifact_unavailable",
            disposition=ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
            message="disk extraction artifact is unavailable",
        )
    if error.errno in {errno.ELOOP, errno.ENOTDIR}:
        return ExtractionArtifactReaderError(
            code="unsafe_artifact_path",
            disposition=ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
            message="disk extraction artifact path is unsafe",
        )
    if error.errno in {errno.EACCES, errno.EPERM}:
        return ExtractionArtifactReaderError(
            code="artifact_read_authority_required",
            disposition=ExtractionActionDisposition.AUTHORITY_REQUIRED,
            message="disk extraction artifact cannot be accessed",
        )
    return ExtractionArtifactReaderError(
        code="artifact_read_failed",
        disposition=ExtractionActionDisposition.RETRY_SAME_REQUEST,
        message="disk extraction artifact could not be read",
    )

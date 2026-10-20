"""Descriptor-anchored reads of immutable publication objects."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from projectkoios.ingestion.page.projection.publication.load.error import (
    PageProjectionPublicationLoadError,
    PageProjectionPublicationLoadFailureReason,
)
from projectkoios.ingestion.page.projection.publication.load.request import (
    PageProjectionPublicationLoadRequest,
)
from projectkoios.ingestion.page.projection.publication.load.source import (
    PageProjectionPublicationLoadBytes,
    PageProjectionPublicationPayloadSource,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash

_READ_CHUNK_BYTES = 1_048_576


class DiskPageProjectionPublicationPayloadSource(
    PageProjectionPublicationPayloadSource
):
    """Read exact immutable receipt and payload objects without head lookup."""

    __slots__ = ("_root_device", "_root_inode", "root")

    IMPLEMENTATION_ID = "disk-page-projection-publication-payload-source:1.0"

    def __init__(self, *, root: Path) -> None:
        if not isinstance(root, Path):
            raise TypeError("root must be a Path")
        expanded = root.expanduser()
        if len(os.fsencode(expanded)) > 4_096:
            raise ValueError("publication root exceeds its limit")
        if expanded.is_symlink():
            raise ValueError("publication root cannot be a symlink")
        resolved: Path | None
        try:
            resolved = expanded.resolve(strict=True)
            root_status = resolved.stat(follow_symlinks=False)
        except OSError:
            resolved = None
            root_status = None
        if (
            resolved is None
            or root_status is None
            or not stat.S_ISDIR(root_status.st_mode)
        ):
            raise ValueError("publication root is unavailable")
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            raise RuntimeError(
                "secure descriptor-relative disk access is unavailable"
            )
        self.root = resolved
        self._root_device = root_status.st_dev
        self._root_inode = root_status.st_ino

    @property
    def implementation_id(self) -> str:
        """Return the exact read-only disk source identity."""
        return self.IMPLEMENTATION_ID

    def load(
        self,
        *,
        request: PageProjectionPublicationLoadRequest,
    ) -> PageProjectionPublicationLoadBytes:
        """Read exact objects selected only by immutable request digests."""
        if type(request) is not PageProjectionPublicationLoadRequest:
            raise TypeError("request has an unsupported type")
        receipt: bytes | None = None
        try:
            receipt = read_immutable_publication_object(
                root=self.root,
                root_device=self._root_device,
                root_inode=self._root_inode,
                collection="receipts",
                digest=request.expected_receipt_sha256,
                expected_byte_length=request.expected_receipt_byte_length,
                maximum_bytes=request.expected_receipt_byte_length,
            )
        except OSError, TypeError, ValueError:
            pass
        if receipt is None:
            raise PageProjectionPublicationLoadError(
                reason=(
                    PageProjectionPublicationLoadFailureReason.RECEIPT_UNAVAILABLE
                ),
                message="immutable publication receipt is unavailable",
            )
        payload: bytes | None = None
        try:
            payload = read_immutable_publication_object(
                root=self.root,
                root_device=self._root_device,
                root_inode=self._root_inode,
                collection="objects",
                digest=request.expected_payload_sha256,
                expected_byte_length=request.expected_payload_byte_length,
                maximum_bytes=request.maximum_payload_bytes,
            )
        except OSError, TypeError, ValueError:
            pass
        if payload is None:
            raise PageProjectionPublicationLoadError(
                reason=(
                    PageProjectionPublicationLoadFailureReason.PAYLOAD_UNAVAILABLE
                ),
                message="immutable publication payload is unavailable",
            )
        return PageProjectionPublicationLoadBytes(
            receipt=receipt,
            payload=payload,
        )


def read_immutable_publication_object(
    *,
    root: Path,
    root_device: int,
    root_inode: int,
    collection: str,
    digest: str,
    expected_byte_length: int,
    maximum_bytes: int,
) -> bytes:
    """Read one bounded object through one descriptor-anchored traversal."""
    if collection not in {"objects", "receipts"}:
        raise ValueError("publication object collection is unsupported")
    if not SHA256Hash.is_canonical(digest):
        raise ValueError("publication object digest is invalid")
    for value, name in (
        (root_device, "root_device"),
        (root_inode, "root_inode"),
        (expected_byte_length, "expected_byte_length"),
        (maximum_bytes, "maximum_bytes"),
    ):
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} is invalid")
    if expected_byte_length > maximum_bytes:
        raise ValueError("publication object exceeds its declared ceiling")
    descriptors: list[int] = []
    try:
        directory_flags = (
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        descriptors.append(os.open(root.anchor, directory_flags))
        for root_part in root.parts[1:]:
            descriptors.append(
                os.open(
                    root_part,
                    directory_flags,
                    dir_fd=descriptors[-1],
                )
            )
        root_status = os.fstat(descriptors[-1])
        if (
            root_status.st_dev != root_device
            or root_status.st_ino != root_inode
        ):
            raise OSError("publication root identity changed")
        for directory_part in (collection, digest[:2]):
            descriptors.append(
                os.open(
                    directory_part,
                    directory_flags,
                    dir_fd=descriptors[-1],
                )
            )
        descriptors.append(
            os.open(
                f"{digest}.json",
                file_flags,
                dir_fd=descriptors[-1],
            )
        )
        descriptor = descriptors[-1]
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError("publication object is not a regular file")
        if (
            before.st_size != expected_byte_length
            or before.st_size > maximum_bytes
        ):
            raise ValueError("publication object byte length differs")
        chunks: list[bytes] = []
        observed = 0
        while True:
            chunk = os.read(descriptor, _READ_CHUNK_BYTES)
            if not chunk:
                break
            observed += len(chunk)
            if observed > maximum_bytes:
                raise ValueError("publication object exceeds its byte ceiling")
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (
            observed != expected_byte_length
            or observed != before.st_size
            or after.st_dev != before.st_dev
            or after.st_ino != before.st_ino
            or after.st_size != before.st_size
            or after.st_mtime_ns != before.st_mtime_ns
            or after.st_ctime_ns != before.st_ctime_ns
        ):
            raise OSError("publication object changed during read")
        return b"".join(chunks)
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass

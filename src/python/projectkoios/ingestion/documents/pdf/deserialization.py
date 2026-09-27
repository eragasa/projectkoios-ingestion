from __future__ import annotations

import errno
import os
import stat
from abc import ABC, abstractmethod
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

from projectkoios.ingestion.base import BaseProcessedDocument


class BaseDeserializer:
    """Shared bounded deserialization operations."""

    @staticmethod
    def _positive_limit(value: int, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return value

    @staticmethod
    def _read_regular_file(
        path: Path,
        *,
        limit: int,
        label: str,
    ) -> bytes:
        if not isinstance(path, Path):
            raise TypeError(f"{label} path must be a Path")
        source = path.expanduser().absolute()
        descriptor = BaseDeserializer._open_without_links(source, label)
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError(
                    f"{label} must be a non-symlinked regular file"
                )
            if before.st_size > limit:
                raise ValueError(f"{label} exceeds its byte limit")
            chunks: list[bytes] = []
            size = 0
            while True:
                chunk = os.read(descriptor, min(65_536, limit + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > limit:
                    raise ValueError(f"{label} exceeds its byte limit")
            after = os.fstat(descriptor)
            before_identity = (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            after_identity = (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            if before_identity != after_identity or size != after.st_size:
                raise ValueError(f"{label} changed while it was read")
            return b"".join(chunks)
        finally:
            os.close(descriptor)

    @staticmethod
    def _open_without_links(source: Path, label: str) -> int:
        """Open one path without following links in any component."""
        file_flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        nofollow_any = getattr(os, "O_NOFOLLOW_ANY", None)
        if nofollow_any is not None:
            try:
                return os.open(source, file_flags | nofollow_any)
            except OSError as error:
                BaseDeserializer._raise_path_open_error(
                    source,
                    label,
                    error,
                )

        nofollow = getattr(os, "O_NOFOLLOW", None)
        directory = getattr(os, "O_DIRECTORY", None)
        if (
            nofollow is None
            or directory is None
            or os.open not in os.supports_dir_fd
        ):
            raise OSError(
                errno.ENOTSUP,
                "race-safe opening without symbolic links or reparse points "
                "is unavailable on this platform",
                source,
            )

        directory_flags = file_flags | nofollow | directory
        components = list(source.parts[1:])
        leaf = components.pop() if components else "."
        descriptors = [os.open(source.anchor, directory_flags)]
        try:
            for component in components:
                if component == "..":
                    if len(descriptors) > 1:
                        os.close(descriptors.pop())
                    continue
                descriptors.append(
                    BaseDeserializer._open_path_component(
                        component,
                        directory_flags,
                        descriptors[-1],
                        label,
                    )
                )
            if leaf == "..":
                if len(descriptors) > 1:
                    os.close(descriptors.pop())
                return os.dup(descriptors[-1])
            return BaseDeserializer._open_path_component(
                leaf,
                file_flags | nofollow,
                descriptors[-1],
                label,
            )
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    @staticmethod
    def _open_path_component(
        component: str,
        flags: int,
        parent_descriptor: int,
        label: str,
    ) -> int:
        try:
            return os.open(component, flags, dir_fd=parent_descriptor)
        except OSError as error:
            BaseDeserializer._raise_path_open_error(
                component,
                label,
                error,
                dir_fd=parent_descriptor,
            )

    @staticmethod
    def _raise_path_open_error(
        path: str | Path,
        label: str,
        error: OSError,
        *,
        dir_fd: int | None = None,
    ) -> NoReturn:
        link_error_numbers = {errno.ELOOP}
        if hasattr(errno, "EMLINK"):
            link_error_numbers.add(errno.EMLINK)
        is_link = error.errno in link_error_numbers
        if not is_link:
            try:
                opened = os.stat(
                    path,
                    dir_fd=dir_fd,
                    follow_symlinks=False,
                )
            except OSError:
                pass
            else:
                attributes = getattr(opened, "st_file_attributes", 0)
                is_link = stat.S_ISLNK(opened.st_mode) or bool(
                    attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
                )
        if is_link:
            raise ValueError(
                f"{label} must not traverse a symbolic link or reparse point"
            ) from error
        raise error

    @staticmethod
    def _resolve_location(
        root: Path,
        relative: PurePosixPath,
        field: str,
    ) -> Path:
        unresolved = root.joinpath(*relative.parts)
        resolved = unresolved.resolve(strict=True)
        if not resolved.is_relative_to(root) or resolved != unresolved:
            raise ValueError(f"{field} escapes its root or traverses a symlink")
        return resolved


class BaseProcessedDocumentDeserializer[
    ProcessedDocumentT: BaseProcessedDocument,
](BaseDeserializer, ABC):
    """Reconstruct one verified processed document from explicit locations."""

    @abstractmethod
    def deserialize(
        self,
        *,
        citation_key: str,
        bibtex_path: Path,
        pdf_path: Path,
        processed_document_path: Path,
    ) -> ProcessedDocumentT:
        """Deserialize one processed document without location discovery."""


class BaseProcessedDocumentsDeserializer[
    ProcessedDocumentT: BaseProcessedDocument,
    ProcessedDocumentsT,
](BaseDeserializer, ABC):
    """Reconstruct an ordered collection of BaseProcessedDocument values."""

    @abstractmethod
    def deserialize(self, manifest_path: Path) -> ProcessedDocumentsT:
        """Deserialize an explicit ordered collection manifest."""

    @staticmethod
    def _object_without_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    @staticmethod
    def _reject_json_constant(value: str) -> NoReturn:
        raise ValueError(f"invalid JSON number: {value}")


__all__ = [
    "BaseDeserializer",
    "BaseProcessedDocumentDeserializer",
    "BaseProcessedDocumentsDeserializer",
]

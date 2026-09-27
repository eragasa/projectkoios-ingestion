from __future__ import annotations

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
        nofollow = getattr(os, "O_NOFOLLOW", None)
        if nofollow is None:  # pragma: no cover - platform capability guard
            raise OSError("no-follow file opening is unavailable")
        source = path.expanduser().absolute()
        flags = (
            os.O_RDONLY
            | nofollow
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        descriptor = os.open(source, flags)
        try:
            before = os.fstat(descriptor)
            BaseDeserializer._require_opened_path(
                source,
                before,
                label,
            )
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
            BaseDeserializer._require_opened_path(
                source,
                after,
                label,
            )
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
    def _require_opened_path(
        source: Path,
        opened: os.stat_result,
        label: str,
    ) -> None:
        if source.resolve(strict=True) != source:
            raise ValueError(f"{label} must not traverse a symbolic link")
        current = os.stat(source, follow_symlinks=False)
        if current.st_dev != opened.st_dev or current.st_ino != opened.st_ino:
            raise ValueError(f"{label} changed while it was opened")

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

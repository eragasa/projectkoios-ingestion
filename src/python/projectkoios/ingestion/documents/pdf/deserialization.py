from __future__ import annotations

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
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"{label} must be a non-symlinked regular file")
        size = source.stat().st_size
        if size > limit:
            raise ValueError(f"{label} exceeds its byte limit")
        content = source.read_bytes()
        if len(content) != size or len(content) > limit:
            raise ValueError(f"{label} changed while it was read")
        return content

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

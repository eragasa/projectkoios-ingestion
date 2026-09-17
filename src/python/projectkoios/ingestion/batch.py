from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

_MAX_BATCH_ITEMS = 256
_MAX_IDENTITY_LENGTH = 4096
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _relative_path(value: object, *, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    if len(value) > _MAX_IDENTITY_LENGTH:
        raise ValueError(f"{field} is too long")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"{field} must be a safe relative path")
    if any(part in ("", ".") for part in path.parts):
        raise ValueError(f"{field} must be normalized")
    if path.as_posix() != value:
        raise ValueError(f"{field} must be normalized")
    return path


@dataclass(frozen=True)
class PdfBatchItem:
    source_id: str
    pdf_path: PurePosixPath
    output_directory: PurePosixPath
    sha256: str
    byte_size: int
    locator: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_id, str)
            or not self.source_id
            or len(self.source_id) > _MAX_IDENTITY_LENGTH
        ):
            raise ValueError("source_id must be a bounded non-empty string")
        for field, path in (
            ("pdf_path", self.pdf_path),
            ("output_directory", self.output_directory),
        ):
            if not isinstance(path, PurePosixPath):
                raise ValueError(f"{field} must be a portable path")
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or any(part in ("", ".") for part in path.parts)
            ):
                raise ValueError(f"{field} must be a safe relative path")
        if self.pdf_path.suffix.lower() != ".pdf":
            raise ValueError("pdf_path must name a PDF")
        if not isinstance(self.sha256, str) or not _SHA256.fullmatch(
            self.sha256
        ):
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        if (
            isinstance(self.byte_size, bool)
            or not isinstance(self.byte_size, int)
            or self.byte_size <= 0
        ):
            raise ValueError("byte_size must be a positive integer")
        if self.locator is not None and (
            not isinstance(self.locator, str)
            or not self.locator
            or len(self.locator) > _MAX_IDENTITY_LENGTH
        ):
            raise ValueError("locator must be a bounded non-empty string")

    @classmethod
    def from_dict(cls, value: object) -> PdfBatchItem:
        if not isinstance(value, dict):
            raise ValueError("batch item must be an object")
        expected = {
            "source_id",
            "pdf_path",
            "output_directory",
            "sha256",
            "byte_size",
            "locator",
        }
        unknown = set(value) - expected
        if unknown:
            raise ValueError(f"unknown batch item fields: {sorted(unknown)}")
        source_id = value.get("source_id")
        locator = value.get("locator")
        if not isinstance(source_id, str):
            raise ValueError("source_id must be a string")
        if locator is not None and not isinstance(locator, str):
            raise ValueError("locator must be a string or null")
        sha256 = value.get("sha256")
        byte_size = value.get("byte_size")
        if not isinstance(sha256, str):
            raise ValueError("sha256 must be a string")
        if type(byte_size) is not int:
            raise ValueError("byte_size must be an integer")
        return cls(
            source_id=source_id,
            pdf_path=_relative_path(value.get("pdf_path"), field="pdf_path"),
            output_directory=_relative_path(
                value.get("output_directory"), field="output_directory"
            ),
            sha256=sha256,
            byte_size=byte_size,
            locator=locator,
        )


@dataclass(frozen=True)
class PdfBatchPlan:
    schema_version: int
    items: tuple[PdfBatchItem, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported PDF batch-plan schema version")
        if not isinstance(self.items, tuple) or not self.items:
            raise ValueError("PDF batch plan must contain an item tuple")
        if any(not isinstance(item, PdfBatchItem) for item in self.items):
            raise ValueError("PDF batch plan items must be PdfBatchItem values")
        if len(self.items) > _MAX_BATCH_ITEMS:
            raise ValueError("PDF batch plan exceeds the item limit")
        self._require_unique(
            "source_id", tuple(item.source_id for item in self.items)
        )
        self._require_unique(
            "pdf_path", tuple(item.pdf_path.as_posix() for item in self.items)
        )
        self._require_unique(
            "output_directory",
            tuple(item.output_directory.as_posix() for item in self.items),
        )

    @staticmethod
    def _require_unique(field: str, values: tuple[str, ...]) -> None:
        if len(values) != len(set(values)):
            raise ValueError(
                f"PDF batch plan contains duplicate {field} values"
            )

    @classmethod
    def from_json(cls, text: str) -> PdfBatchPlan:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("PDF batch plan must be an object")
        unknown = set(data) - {"schema_version", "items"}
        if unknown:
            raise ValueError(
                f"unknown PDF batch-plan fields: {sorted(unknown)}"
            )
        schema_version = data.get("schema_version")
        items = data.get("items")
        if type(schema_version) is not int:
            raise ValueError("schema_version must be an integer")
        if not isinstance(items, list):
            raise ValueError("items must be an array")
        return cls(
            schema_version=schema_version,
            items=tuple(PdfBatchItem.from_dict(item) for item in items),
        )

    def to_json(self) -> str:
        value = {
            "schema_version": self.schema_version,
            "items": [
                {
                    "source_id": item.source_id,
                    "pdf_path": item.pdf_path.as_posix(),
                    "output_directory": item.output_directory.as_posix(),
                    "sha256": item.sha256,
                    "byte_size": item.byte_size,
                    "locator": item.locator,
                }
                for item in self.items
            ],
        }
        return json.dumps(value, ensure_ascii=False, indent=2) + "\n"

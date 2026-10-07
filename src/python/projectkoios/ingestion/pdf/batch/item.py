"""Immutable portable PDF batch source declaration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from projectkoios.ingestion.pdf.batch.limits.definition import (
    MAX_PDF_BATCH_TEXT_CHARACTERS,
)
from projectkoios.ingestion.pdf.batch.limits.error import PdfBatchLimitError
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class PdfBatchItem:
    """Declare one bounded PDF source and its portable output target."""

    source_id: str
    pdf_path: PurePosixPath
    output_directory: PurePosixPath
    sha256: str
    byte_size: int
    locator: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise ValueError("source_id must be a bounded non-empty string")
        if len(self.source_id) > MAX_PDF_BATCH_TEXT_CHARACTERS:
            raise PdfBatchLimitError(
                "source_id must be a bounded non-empty string"
            )
        for field, path in (
            ("pdf_path", self.pdf_path),
            ("output_directory", self.output_directory),
        ):
            if not isinstance(path, PurePosixPath):
                raise ValueError(f"{field} must be a portable path")
            if len(path.as_posix()) > MAX_PDF_BATCH_TEXT_CHARACTERS:
                raise PdfBatchLimitError(f"{field} is too long")
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or any(part in ("", ".") for part in path.parts)
            ):
                raise ValueError(f"{field} must be a safe relative path")
        if self.pdf_path.suffix.lower() != ".pdf":
            raise ValueError("pdf_path must name a PDF")
        if not isinstance(self.sha256, str) or not SHA256Hash.is_canonical(
            self.sha256
        ):
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        if (
            isinstance(self.byte_size, bool)
            or not isinstance(self.byte_size, int)
            or self.byte_size <= 0
        ):
            raise ValueError("byte_size must be a positive integer")
        if self.locator is not None:
            if not isinstance(self.locator, str) or not self.locator:
                raise ValueError("locator must be a bounded non-empty string")
            if len(self.locator) > MAX_PDF_BATCH_TEXT_CHARACTERS:
                raise PdfBatchLimitError(
                    "locator must be a bounded non-empty string"
                )

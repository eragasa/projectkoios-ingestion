"""One source and its selected OCR reconciliation pages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.batch import PdfBatchItem
from projectkoios.ingestion.ocr.reconciliation.batch.page import (
    SelectiveOCRReconciliationPage,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash

_MAX_PAGES_PER_ITEM = 1_024
_MAX_PATH_CHARACTERS = 4_096


@dataclass(frozen=True, slots=True)
class SelectiveOCRReconciliationItem(AbstractImmutableDataObject):
    """Hash-locked extraction and OCR evidence selected for reconciliation."""

    source: PdfBatchItem
    extraction_sha256: str
    ocr_directory: PurePosixPath
    output_directory: PurePosixPath
    pages: tuple[SelectiveOCRReconciliationPage, ...]

    def __post_init__(self) -> None:
        if type(self.source) is not PdfBatchItem:
            raise TypeError("reconciliation source must be a PdfBatchItem")
        if not SHA256Hash.is_canonical(self.extraction_sha256):
            raise ValueError(
                "reconciliation extraction SHA-256 must be lowercase"
            )
        _validate_directory(self.ocr_directory, "OCR")
        _validate_directory(self.output_directory, "output")
        if type(self.pages) is not tuple or not self.pages:
            raise ValueError("reconciliation pages must be a non-empty tuple")
        if len(self.pages) > _MAX_PAGES_PER_ITEM:
            raise ValueError("reconciliation item exceeds its page limit")
        if any(
            type(page) is not SelectiveOCRReconciliationPage
            for page in self.pages
        ):
            raise TypeError("reconciliation pages must be typed")
        indices = tuple(page.page_index for page in self.pages)
        if indices != tuple(sorted(set(indices))):
            raise ValueError(
                "reconciliation pages must be unique and strictly ordered"
            )

    @classmethod
    def from_dict(cls, value: object) -> SelectiveOCRReconciliationItem:
        expected = {
            "source",
            "extraction_sha256",
            "ocr_directory",
            "output_directory",
            "pages",
        }
        if type(value) is not dict or set(value) != expected:
            raise ValueError("reconciliation item has an invalid shape")
        extraction_sha256 = value["extraction_sha256"]
        ocr_directory = value["ocr_directory"]
        output_directory = value["output_directory"]
        pages = value["pages"]
        if (
            not isinstance(extraction_sha256, str)
            or type(ocr_directory) is not str
            or type(output_directory) is not str
        ):
            raise TypeError("reconciliation item fields have invalid types")
        if type(pages) is not list:
            raise TypeError("reconciliation pages must be an array")
        return cls(
            source=PdfBatchItem.from_dict(value["source"]),
            extraction_sha256=extraction_sha256,
            ocr_directory=PurePosixPath(ocr_directory),
            output_directory=PurePosixPath(output_directory),
            pages=tuple(
                SelectiveOCRReconciliationPage.from_dict(page) for page in pages
            ),
        )


def _validate_directory(path: PurePosixPath, label: str) -> None:
    if not isinstance(path, PurePosixPath):
        raise TypeError(f"reconciliation {label} directory must be portable")
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or any(part in ("", ".") for part in path.parts)
        or len(path.as_posix()) > _MAX_PATH_CHARACTERS
    ):
        raise ValueError(f"reconciliation {label} directory must be safe")

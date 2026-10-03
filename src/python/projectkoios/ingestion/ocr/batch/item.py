"""One source document and its explicit selective OCR pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.batch import PdfBatchItem
from projectkoios.ingestion.ocr.batch.page import SelectiveOCRPage

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_PAGES_PER_ITEM = 1_024
_MAX_PATH_CHARACTERS = 4_096


@dataclass(frozen=True, slots=True)
class SelectiveOCRItem(AbstractImmutableDataObject):
    """Hash-locked source/extraction evidence and selected pages."""

    source: PdfBatchItem
    extraction_sha256: str
    output_directory: PurePosixPath
    pages: tuple[SelectiveOCRPage, ...]

    def __post_init__(self) -> None:
        if type(self.source) is not PdfBatchItem:
            raise TypeError("selective OCR source must be a PdfBatchItem")
        if type(self.extraction_sha256) is not str or not _SHA256.fullmatch(
            self.extraction_sha256
        ):
            raise ValueError(
                "selective OCR extraction SHA-256 must be lowercase"
            )
        _validate_output_directory(self.output_directory)
        if type(self.pages) is not tuple or not self.pages:
            raise ValueError("selective OCR pages must be a non-empty tuple")
        if len(self.pages) > _MAX_PAGES_PER_ITEM:
            raise ValueError("selective OCR item exceeds its page limit")
        if any(type(page) is not SelectiveOCRPage for page in self.pages):
            raise TypeError("selective OCR pages must be typed")
        indices = tuple(page.page_index for page in self.pages)
        if indices != tuple(sorted(set(indices))):
            raise ValueError(
                "selective OCR pages must be unique and strictly ordered"
            )

    @classmethod
    def from_dict(cls, value: object) -> SelectiveOCRItem:
        expected = {
            "source",
            "extraction_sha256",
            "output_directory",
            "pages",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("selective OCR item has an invalid shape")
        extraction_sha256 = value["extraction_sha256"]
        output_directory = value["output_directory"]
        pages = value["pages"]
        if type(extraction_sha256) is not str:
            raise TypeError("extraction_sha256 must be a string")
        if type(output_directory) is not str:
            raise TypeError("output_directory must be a string")
        if not isinstance(pages, list):
            raise TypeError("pages must be an array")
        return cls(
            source=PdfBatchItem.from_dict(value["source"]),
            extraction_sha256=extraction_sha256,
            output_directory=PurePosixPath(output_directory),
            pages=tuple(SelectiveOCRPage.from_dict(page) for page in pages),
        )


def _validate_output_directory(path: PurePosixPath) -> None:
    if not isinstance(path, PurePosixPath):
        raise TypeError("selective OCR output directory must be portable")
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or any(part in ("", ".") for part in path.parts)
        or len(path.as_posix()) > _MAX_PATH_CHARACTERS
    ):
        raise ValueError("selective OCR output directory must be safe")

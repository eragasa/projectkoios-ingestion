"""One hash-locked OCR page selected for reconciliation."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class SelectiveOCRReconciliationPage(AbstractImmutableDataObject):
    """Zero-based page index and exact selective OCR publication digest."""

    page_index: int
    ocr_publication_sha256: str

    def __post_init__(self) -> None:
        if type(self.page_index) is not int:
            raise TypeError("reconciliation page index must be an integer")
        if self.page_index < 0:
            raise ValueError("reconciliation page index must be nonnegative")
        if not SHA256Hash.is_canonical(self.ocr_publication_sha256):
            raise ValueError("OCR publication SHA-256 must be lowercase")

    @classmethod
    def from_dict(cls, value: object) -> SelectiveOCRReconciliationPage:
        if type(value) is not dict or set(value) != {
            "page_index",
            "ocr_publication_sha256",
        }:
            raise ValueError("reconciliation page has an invalid shape")
        page_index = value["page_index"]
        digest = value["ocr_publication_sha256"]
        if type(page_index) is not int or not isinstance(digest, str):
            raise TypeError("reconciliation page fields have invalid types")
        return cls(page_index=page_index, ocr_publication_sha256=digest)

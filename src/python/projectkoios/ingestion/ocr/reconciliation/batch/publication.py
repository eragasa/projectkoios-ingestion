"""Durable publication of one selective OCR reconciliation result."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.ocr.reconciliation.batch.item import (
    SelectiveOCRReconciliationItem,
)
from projectkoios.ingestion.ocr.reconciliation.batch.page import (
    SelectiveOCRReconciliationPage,
)
from projectkoios.ingestion.reconciliation.result import OCRReconciliationResult

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class SelectiveOCRReconciliationPublication(AbstractImmutableDataObject):
    """Exact extraction/OCR linkage plus one reconciliation result."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"

    publication_id: str
    source_id: str
    source_sha256: str
    extraction_sha256: str
    ocr_publication_sha256: str
    page_index: int
    result: OCRReconciliationResult

    @classmethod
    def create(
        cls,
        *,
        item: SelectiveOCRReconciliationItem,
        page: SelectiveOCRReconciliationPage,
        result: OCRReconciliationResult,
    ) -> SelectiveOCRReconciliationPublication:
        if type(item) is not SelectiveOCRReconciliationItem:
            raise TypeError("reconciliation publication item must be typed")
        if type(page) is not SelectiveOCRReconciliationPage:
            raise TypeError("reconciliation publication page must be typed")
        if type(result) is not OCRReconciliationResult:
            raise TypeError("reconciliation publication result must be typed")
        return cls(
            publication_id=stable_id(
                "selective-ocr-reconciliation-publication",
                cls.CONTRACT_VERSION,
                item.source.source_id,
                item.source.sha256,
                item.extraction_sha256,
                page.ocr_publication_sha256,
                page.page_index,
                result.result_id,
            ),
            source_id=item.source.source_id,
            source_sha256=item.source.sha256,
            extraction_sha256=item.extraction_sha256,
            ocr_publication_sha256=page.ocr_publication_sha256,
            page_index=page.page_index,
            result=result,
        )

    def __post_init__(self) -> None:
        if type(self.source_id) is not str or not self.source_id:
            raise ValueError("reconciliation source ID is invalid")
        for name, value in (
            ("source SHA-256", self.source_sha256),
            ("extraction SHA-256", self.extraction_sha256),
            ("OCR publication SHA-256", self.ocr_publication_sha256),
        ):
            if type(value) is not str or not _SHA256.fullmatch(value):
                raise ValueError(f"reconciliation {name} is invalid")
        if type(self.page_index) is not int:
            raise TypeError(
                "reconciliation publication page must be an integer"
            )
        if self.page_index < 0:
            raise ValueError(
                "reconciliation publication page must be nonnegative"
            )
        if type(self.result) is not OCRReconciliationResult:
            raise TypeError("reconciliation publication result must be typed")
        selection = self.result.reconciliation_input.selection
        region = selection.image.rendered_region
        if (
            region.source_id != self.source_id
            or region.source_content_hash != self.source_sha256
            or region.source_blob_id != f"blob:sha256:{self.source_sha256}"
            or region.page_index != self.page_index
        ):
            raise ValueError(
                "reconciliation publication linkage is inconsistent"
            )
        expected = stable_id(
            "selective-ocr-reconciliation-publication",
            self.CONTRACT_VERSION,
            self.source_id,
            self.source_sha256,
            self.extraction_sha256,
            self.ocr_publication_sha256,
            self.page_index,
            self.result.result_id,
        )
        if self.publication_id != expected:
            raise ValueError("reconciliation publication ID is inconsistent")

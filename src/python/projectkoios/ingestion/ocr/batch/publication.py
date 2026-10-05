"""Durable publication of one selective OCR page result."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.ocr.batch.item import SelectiveOCRItem
from projectkoios.ingestion.ocr.batch.page import SelectiveOCRPage
from projectkoios.ingestion.ocr.result import OCRResult
from projectkoios.ingestion.ocr.serialization import (
    deserialize_ocr_result,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class SelectiveOCRPublication(AbstractImmutableDataObject):
    """Exact plan/source/extraction linkage plus one OCR result."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"

    publication_id: str
    source_sha256: str
    extraction_sha256: str
    page_index: int
    result: OCRResult

    @classmethod
    def create(
        cls,
        *,
        item: SelectiveOCRItem,
        page: SelectiveOCRPage,
        result: OCRResult,
    ) -> SelectiveOCRPublication:
        if type(item) is not SelectiveOCRItem:
            raise TypeError("selective OCR publication item must be typed")
        if type(page) is not SelectiveOCRPage:
            raise TypeError("selective OCR publication page must be typed")
        if type(result) is not OCRResult:
            raise TypeError("selective OCR publication result must be typed")
        publication_id = stable_id(
            "selective-ocr-publication",
            cls.CONTRACT_VERSION,
            item.source.sha256,
            item.extraction_sha256,
            page.page_index,
            result.result_id,
        )
        return cls(
            publication_id=publication_id,
            source_sha256=item.source.sha256,
            extraction_sha256=item.extraction_sha256,
            page_index=page.page_index,
            result=result,
        )

    @classmethod
    def from_dict(cls, value: object) -> SelectiveOCRPublication:
        expected = {
            "publication_id",
            "source_sha256",
            "extraction_sha256",
            "page_index",
            "result",
        }
        if type(value) is not dict or set(value) != expected:
            raise ValueError("selective OCR publication has an invalid shape")
        publication_id = value["publication_id"]
        source_sha256 = value["source_sha256"]
        extraction_sha256 = value["extraction_sha256"]
        page_index = value["page_index"]
        if type(publication_id) is not str:
            raise TypeError("selective OCR publication ID must be a string")
        if type(source_sha256) is not str or type(extraction_sha256) is not str:
            raise TypeError("selective OCR publication hashes must be strings")
        if type(page_index) is not int:
            raise TypeError("selective OCR publication page must be an integer")
        return cls(
            publication_id=publication_id,
            source_sha256=source_sha256,
            extraction_sha256=extraction_sha256,
            page_index=page_index,
            result=deserialize_ocr_result(value["result"]),
        )

    def __post_init__(self) -> None:
        for name, value in (
            ("source SHA-256", self.source_sha256),
            ("extraction SHA-256", self.extraction_sha256),
        ):
            if type(value) is not str or not _SHA256.fullmatch(value):
                raise ValueError(f"selective OCR {name} is invalid")
        if isinstance(self.page_index, bool) or not isinstance(
            self.page_index,
            int,
        ):
            raise TypeError("selective OCR publication page must be an integer")
        if self.page_index < 0:
            raise ValueError(
                "selective OCR publication page must be nonnegative"
            )
        if type(self.result) is not OCRResult:
            raise TypeError("selective OCR publication result must be typed")
        selections = self.result.request.selections
        if len(selections) != 1:
            raise ValueError("selective OCR publication requires one selection")
        region = selections[0].image.rendered_region
        if (
            region.source_content_hash != self.source_sha256
            or region.page_index != self.page_index
        ):
            raise ValueError(
                "selective OCR publication source linkage is inconsistent"
            )
        expected = stable_id(
            "selective-ocr-publication",
            self.CONTRACT_VERSION,
            self.source_sha256,
            self.extraction_sha256,
            self.page_index,
            self.result.result_id,
        )
        if self.publication_id != expected:
            raise ValueError("selective OCR publication ID is inconsistent")

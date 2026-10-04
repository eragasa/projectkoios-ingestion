"""Ownership and nominal-base checks for OCRResult."""

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.ocr.result import OCRResult


def test__owned_module_and_nominal_base() -> None:
    assert OCRResult.__module__ == "projectkoios.ingestion.ocr.result"
    assert issubclass(OCRResult, DataObjectActionResult)

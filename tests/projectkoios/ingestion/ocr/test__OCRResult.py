"""Ownership and nominal-base checks for OCRResult."""

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.ocr.result.ocr import OCRResult


def test__owned_module_and_nominal_base() -> None:
    assert OCRResult.__module__ == "projectkoios.ingestion.ocr.result.ocr"
    assert issubclass(OCRResult, DataObjectActionResult)

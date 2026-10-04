"""Ownership and nominal-base checks for OCRRequest."""

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.ocr.request import OCRRequest


def test__owned_module_and_nominal_base() -> None:
    assert OCRRequest.__module__ == "projectkoios.ingestion.ocr.request"
    assert issubclass(OCRRequest, DataObjectActionRequest)

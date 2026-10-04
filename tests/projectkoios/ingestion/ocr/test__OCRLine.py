"""Ownership and nominal-base checks for OCRLine."""

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.line import OCRLine


def test__owned_module_and_nominal_base() -> None:
    assert OCRLine.__module__ == "projectkoios.ingestion.ocr.line"
    assert issubclass(OCRLine, AbstractImmutableDataObject)
    from projectkoios.ingestion.ocr.base import OCRTextOutput

    assert issubclass(OCRLine, OCRTextOutput)

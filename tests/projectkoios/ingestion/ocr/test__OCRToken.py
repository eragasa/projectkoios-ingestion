"""Ownership and nominal-base checks for OCRToken."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.token import OCRToken


def test__owned_module_and_nominal_base() -> None:
    assert OCRToken.__module__ == "projectkoios.ingestion.ocr.token"
    assert issubclass(OCRToken, AbstractImmutableDataObject)
    from projectkoios.ingestion.ocr.base import OCRTextOutput

    assert issubclass(OCRToken, OCRTextOutput)

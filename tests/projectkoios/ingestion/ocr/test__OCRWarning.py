"""Ownership and nominal-base checks for OCRWarning."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.warning import OCRWarning


def test__owned_module_and_nominal_base() -> None:
    assert OCRWarning.__module__ == "projectkoios.ingestion.ocr.warning"
    assert issubclass(OCRWarning, AbstractImmutableDataObject)

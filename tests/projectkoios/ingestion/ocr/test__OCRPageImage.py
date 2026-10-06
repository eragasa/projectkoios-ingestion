"""Ownership and nominal-base checks for OCRPageImage."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.image.page import OCRPageImage


def test__owned_module_and_nominal_base() -> None:
    assert OCRPageImage.__module__ == "projectkoios.ingestion.ocr.image.page"
    assert issubclass(OCRPageImage, AbstractImmutableDataObject)

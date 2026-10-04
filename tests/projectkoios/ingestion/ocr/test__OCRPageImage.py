"""Ownership and nominal-base checks for OCRPageImage."""

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.page_image import OCRPageImage


def test__owned_module_and_nominal_base() -> None:
    assert OCRPageImage.__module__ == "projectkoios.ingestion.ocr.page_image"
    assert issubclass(OCRPageImage, AbstractImmutableDataObject)

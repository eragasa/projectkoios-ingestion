"""Ownership and nominal-base checks for OCRSelection."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.selection import OCRSelection


def test__owned_module_and_nominal_base() -> None:
    assert OCRSelection.__module__ == "projectkoios.ingestion.ocr.selection"
    assert issubclass(OCRSelection, AbstractImmutableDataObject)

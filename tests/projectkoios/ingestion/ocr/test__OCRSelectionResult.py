"""Ownership and nominal-base checks for OCRSelectionResult."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.result.selection import OCRSelectionResult


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRSelectionResult.__module__
        == "projectkoios.ingestion.ocr.result.selection"
    )
    assert issubclass(OCRSelectionResult, AbstractImmutableDataObject)

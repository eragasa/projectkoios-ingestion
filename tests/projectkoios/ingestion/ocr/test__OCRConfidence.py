"""Ownership and nominal-base checks for OCRConfidence."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.confidence import OCRConfidence


def test__owned_module_and_nominal_base() -> None:
    assert OCRConfidence.__module__ == "projectkoios.ingestion.ocr.confidence"
    assert issubclass(OCRConfidence, AbstractImmutableDataObject)

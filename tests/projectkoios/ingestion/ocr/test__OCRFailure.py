"""Ownership and nominal-base checks for OCRFailure."""

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.failure import OCRFailure


def test__owned_module_and_nominal_base() -> None:
    assert OCRFailure.__module__ == "projectkoios.ingestion.ocr.failure"
    assert issubclass(OCRFailure, AbstractImmutableDataObject)

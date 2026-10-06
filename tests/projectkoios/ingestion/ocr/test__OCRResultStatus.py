"""Ownership and nominal-base checks for OCRResultStatus."""

from enum import StrEnum

from projectkoios.ingestion.ocr.status.result import OCRResultStatus


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRResultStatus.__module__ == "projectkoios.ingestion.ocr.status.result"
    )
    assert issubclass(OCRResultStatus, StrEnum)

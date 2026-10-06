"""Ownership and nominal-base checks for OCRSelectionStatus."""

from enum import StrEnum

from projectkoios.ingestion.ocr.status.selection import OCRSelectionStatus


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRSelectionStatus.__module__
        == "projectkoios.ingestion.ocr.status.selection"
    )
    assert issubclass(OCRSelectionStatus, StrEnum)

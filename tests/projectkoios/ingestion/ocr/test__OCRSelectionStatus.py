"""Ownership and nominal-base checks for OCRSelectionStatus."""

from enum import StrEnum

from projectkoios.ingestion.ocr.selection_status import OCRSelectionStatus


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRSelectionStatus.__module__
        == "projectkoios.ingestion.ocr.selection_status"
    )
    assert issubclass(OCRSelectionStatus, StrEnum)

"""Ownership and nominal-base checks for OCRFailureKind."""

from enum import StrEnum

from projectkoios.ingestion.ocr.failure_kind import OCRFailureKind


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRFailureKind.__module__ == "projectkoios.ingestion.ocr.failure_kind"
    )
    assert issubclass(OCRFailureKind, StrEnum)

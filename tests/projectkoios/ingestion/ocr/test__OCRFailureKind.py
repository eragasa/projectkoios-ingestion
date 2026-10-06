"""Ownership and nominal-base checks for OCRFailureKind."""

from enum import StrEnum

from projectkoios.ingestion.ocr.kind.failure import OCRFailureKind


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRFailureKind.__module__ == "projectkoios.ingestion.ocr.kind.failure"
    )
    assert issubclass(OCRFailureKind, StrEnum)

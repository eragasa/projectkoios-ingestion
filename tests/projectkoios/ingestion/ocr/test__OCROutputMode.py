"""Ownership and nominal-base checks for OCROutputMode."""

from enum import StrEnum

from projectkoios.ingestion.ocr.output_mode import OCROutputMode


def test__owned_module_and_nominal_base() -> None:
    assert OCROutputMode.__module__ == "projectkoios.ingestion.ocr.output_mode"
    assert issubclass(OCROutputMode, StrEnum)

"""Ownership and nominal-base checks for OCROutputMode."""

from enum import StrEnum

from projectkoios.ingestion.ocr.mode.output import OCROutputMode


def test__owned_module_and_nominal_base() -> None:
    assert OCROutputMode.__module__ == "projectkoios.ingestion.ocr.mode.output"
    assert issubclass(OCROutputMode, StrEnum)

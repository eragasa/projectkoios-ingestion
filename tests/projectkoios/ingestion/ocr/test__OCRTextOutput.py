"""Ownership and nominal-base checks for OCRTextOutput."""

from abc import ABC

from projectkoios.ingestion.ocr.base import OCRTextOutput


def test__owned_module_and_abstract_base() -> None:
    assert OCRTextOutput.__module__ == "projectkoios.ingestion.ocr.base"
    assert issubclass(OCRTextOutput, ABC)
    assert OCRTextOutput.__abstractmethods__ == frozenset({"output_id"})

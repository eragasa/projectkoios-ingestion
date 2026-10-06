"""Ownership and nominal-base checks for OCRProcessorIdentity."""

from projectkoios.ingestion.base.identity import AbstractIdentity
from projectkoios.ingestion.ocr.identity.processor import OCRProcessorIdentity


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRProcessorIdentity.__module__
        == "projectkoios.ingestion.ocr.identity.processor"
    )
    assert issubclass(OCRProcessorIdentity, AbstractIdentity)

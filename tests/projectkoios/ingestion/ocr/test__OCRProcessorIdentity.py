"""Ownership and nominal-base checks for OCRProcessorIdentity."""

from projectkoios.ingestion.base import AbstractIdentity
from projectkoios.ingestion.ocr.processor_identity import OCRProcessorIdentity


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRProcessorIdentity.__module__
        == "projectkoios.ingestion.ocr.processor_identity"
    )
    assert issubclass(OCRProcessorIdentity, AbstractIdentity)

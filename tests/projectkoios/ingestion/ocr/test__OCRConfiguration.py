"""Ownership and nominal-base checks for OCRConfiguration."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.configuration import OCRConfiguration


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRConfiguration.__module__
        == "projectkoios.ingestion.ocr.configuration"
    )
    assert issubclass(OCRConfiguration, AbstractImmutableDataObject)

"""Ownership and nominal-base checks for OCRNativeTextBlockReference."""

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.native_text_block_reference import (
    OCRNativeTextBlockReference,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRNativeTextBlockReference.__module__
        == "projectkoios.ingestion.ocr.native_text_block_reference"
    )
    assert issubclass(OCRNativeTextBlockReference, AbstractImmutableDataObject)

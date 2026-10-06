"""Ownership and nominal-base checks for OCRNativeTextBlockReference."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr.reference.native.text.block import (
    OCRNativeTextBlockReference,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRNativeTextBlockReference.__module__
        == "projectkoios.ingestion.ocr.reference.native.text.block"
    )
    assert issubclass(OCRNativeTextBlockReference, AbstractImmutableDataObject)

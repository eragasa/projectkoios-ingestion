"""Ownership and nominal-base checks for OCRNativeLineSegment."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.reconciliation.native_line_segment import (
    OCRNativeLineSegment,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRNativeLineSegment.__module__
        == "projectkoios.ingestion.reconciliation.native_line_segment"
    )
    assert issubclass(OCRNativeLineSegment, AbstractImmutableDataObject)

"""Ownership and nominal-base checks for OCRNativeLineSegment."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.reconciliation.segment.native.line import (
    OCRNativeLineSegment,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRNativeLineSegment.__module__
        == "projectkoios.ingestion.reconciliation.segment.native.line"
    )
    assert issubclass(OCRNativeLineSegment, AbstractImmutableDataObject)

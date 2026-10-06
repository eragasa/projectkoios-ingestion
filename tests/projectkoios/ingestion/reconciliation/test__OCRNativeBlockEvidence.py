"""Ownership and nominal-base checks for OCRNativeBlockEvidence."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.reconciliation.evidence.native.block import (
    OCRNativeBlockEvidence,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRNativeBlockEvidence.__module__
        == "projectkoios.ingestion.reconciliation.evidence.native.block"
    )
    assert issubclass(OCRNativeBlockEvidence, AbstractImmutableDataObject)

"""Ownership and nominal-base checks for OCRNativeBlockEvidence."""

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.reconciliation.native_block_evidence import (
    OCRNativeBlockEvidence,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRNativeBlockEvidence.__module__
        == "projectkoios.ingestion.reconciliation.native_block_evidence"
    )
    assert issubclass(OCRNativeBlockEvidence, AbstractImmutableDataObject)

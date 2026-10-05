"""Ownership and nominal-base checks for OCRReconciledItem."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.reconciliation.item import OCRReconciledItem


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRReconciledItem.__module__
        == "projectkoios.ingestion.reconciliation.item"
    )
    assert issubclass(OCRReconciledItem, AbstractImmutableDataObject)

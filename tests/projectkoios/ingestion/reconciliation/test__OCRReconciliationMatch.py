"""Ownership and nominal-base checks for OCRReconciliationMatch."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.reconciliation.match import OCRReconciliationMatch


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRReconciliationMatch.__module__
        == "projectkoios.ingestion.reconciliation.match"
    )
    assert issubclass(OCRReconciliationMatch, AbstractImmutableDataObject)

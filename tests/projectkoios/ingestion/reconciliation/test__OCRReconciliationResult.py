"""Ownership and nominal-base checks for OCRReconciliationResult."""

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.reconciliation.result import OCRReconciliationResult


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRReconciliationResult.__module__
        == "projectkoios.ingestion.reconciliation.result"
    )
    assert issubclass(OCRReconciliationResult, DataObjectActionResult)

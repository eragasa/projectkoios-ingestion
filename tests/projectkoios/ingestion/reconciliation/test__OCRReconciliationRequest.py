"""Ownership and nominal-base checks for OCRReconciliationRequest."""

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.reconciliation.request import (
    OCRReconciliationRequest,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRReconciliationRequest.__module__
        == "projectkoios.ingestion.reconciliation.request"
    )
    assert issubclass(OCRReconciliationRequest, DataObjectActionRequest)

"""Ownership and nominal-base checks for OCRReconciliationLimitError."""

from builtins import ValueError

from projectkoios.ingestion.reconciliation.limit_error import (
    OCRReconciliationLimitError,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRReconciliationLimitError.__module__
        == "projectkoios.ingestion.reconciliation.limit_error"
    )
    assert issubclass(OCRReconciliationLimitError, ValueError)

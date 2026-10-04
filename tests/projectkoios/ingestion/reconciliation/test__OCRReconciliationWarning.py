"""Ownership and nominal-base checks for OCRReconciliationWarning."""

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.reconciliation.warning import (
    OCRReconciliationWarning,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRReconciliationWarning.__module__
        == "projectkoios.ingestion.reconciliation.warning"
    )
    assert issubclass(OCRReconciliationWarning, AbstractImmutableDataObject)

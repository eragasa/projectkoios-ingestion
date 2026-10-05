"""Ownership and nominal-base checks for OCRReconciliationConfiguration."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.reconciliation.configuration import (
    OCRReconciliationConfiguration,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRReconciliationConfiguration.__module__
        == "projectkoios.ingestion.reconciliation.configuration"
    )
    assert issubclass(
        OCRReconciliationConfiguration, AbstractImmutableDataObject
    )

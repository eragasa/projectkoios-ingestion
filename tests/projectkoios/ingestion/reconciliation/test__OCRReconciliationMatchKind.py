"""Ownership and nominal-base checks for OCRReconciliationMatchKind."""

from enum import StrEnum

from projectkoios.ingestion.reconciliation.match_kind import (
    OCRReconciliationMatchKind,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRReconciliationMatchKind.__module__
        == "projectkoios.ingestion.reconciliation.match_kind"
    )
    assert issubclass(OCRReconciliationMatchKind, StrEnum)

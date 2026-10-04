"""Ownership and nominal-base checks for OCRReconciledItemKind."""

from enum import StrEnum

from projectkoios.ingestion.reconciliation.item_kind import (
    OCRReconciledItemKind,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRReconciledItemKind.__module__
        == "projectkoios.ingestion.reconciliation.item_kind"
    )
    assert issubclass(OCRReconciledItemKind, StrEnum)

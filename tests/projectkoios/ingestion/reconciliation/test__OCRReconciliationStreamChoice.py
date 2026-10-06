"""Ownership and nominal-base checks for OCRReconciliationStreamChoice."""

from enum import StrEnum

from projectkoios.ingestion.reconciliation.choice.stream import (
    OCRReconciliationStreamChoice,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRReconciliationStreamChoice.__module__
        == "projectkoios.ingestion.reconciliation.choice.stream"
    )
    assert issubclass(OCRReconciliationStreamChoice, StrEnum)

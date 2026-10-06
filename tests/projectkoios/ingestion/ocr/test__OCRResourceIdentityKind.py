"""Ownership and nominal-base checks for OCRResourceIdentityKind."""

from enum import StrEnum

from projectkoios.ingestion.ocr.kind.resource.identity import (
    OCRResourceIdentityKind,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRResourceIdentityKind.__module__
        == "projectkoios.ingestion.ocr.kind.resource.identity"
    )
    assert issubclass(OCRResourceIdentityKind, StrEnum)

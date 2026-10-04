"""Ownership and nominal-base checks for OCRResourceIdentityKind."""

from enum import StrEnum

from projectkoios.ingestion.ocr.resource_identity_kind import (
    OCRResourceIdentityKind,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRResourceIdentityKind.__module__
        == "projectkoios.ingestion.ocr.resource_identity_kind"
    )
    assert issubclass(OCRResourceIdentityKind, StrEnum)

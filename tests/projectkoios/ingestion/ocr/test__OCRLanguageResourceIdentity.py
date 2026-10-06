"""Ownership and nominal-base checks for OCRLanguageResourceIdentity."""

from projectkoios.ingestion.base.identity import AbstractIdentity
from projectkoios.ingestion.ocr.identity.resource.language import (
    OCRLanguageResourceIdentity,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRLanguageResourceIdentity.__module__
        == "projectkoios.ingestion.ocr.identity.resource.language"
    )
    assert issubclass(OCRLanguageResourceIdentity, AbstractIdentity)

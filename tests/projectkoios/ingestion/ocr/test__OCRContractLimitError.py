"""Ownership and nominal-base checks for OCRContractLimitError."""

from builtins import ValueError

from projectkoios.ingestion.ocr.limit.error import OCRContractLimitError


def test__owned_module_and_nominal_base() -> None:
    assert (
        OCRContractLimitError.__module__
        == "projectkoios.ingestion.ocr.limit.error"
    )
    assert issubclass(OCRContractLimitError, ValueError)

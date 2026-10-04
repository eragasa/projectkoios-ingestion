from dataclasses import fields

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.result.limit_validation import (
    TranscriptionResultLimitValidation,
)


def test__result_limit_validation__retains_bounded_subjects() -> None:
    assert issubclass(TranscriptionResultLimitValidation, AbstractValidation)
    assert {
        field.name for field in fields(TranscriptionResultLimitValidation)
    } >= {
        "items",
        "omissions",
        "warnings",
        "configuration",
    }

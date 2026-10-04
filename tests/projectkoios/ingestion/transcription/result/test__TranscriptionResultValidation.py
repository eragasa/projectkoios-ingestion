from dataclasses import fields

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.result.validation import (
    TranscriptionResultValidation,
)


def test__transcription_result_validation__retains_validation_records() -> None:
    assert issubclass(TranscriptionResultValidation, AbstractValidation)
    assert {field.name for field in fields(TranscriptionResultValidation)} >= {
        "transcription_input",
        "items",
        "omissions",
        "warnings",
        "warning_validation",
        "object_validation",
        "limit_validation",
    }

from dataclasses import fields

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.result.object_validation import (
    TranscriptionResultObjectValidation,
)


def test__result_object_validation__retains_coverage_subjects() -> None:
    assert issubclass(TranscriptionResultObjectValidation, AbstractValidation)
    assert {
        field.name for field in fields(TranscriptionResultObjectValidation)
    } >= {
        "transcription_input",
        "items",
        "omissions",
        "warnings",
    }

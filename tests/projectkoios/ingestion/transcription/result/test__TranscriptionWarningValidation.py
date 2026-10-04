from dataclasses import fields

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.result.warning_validation import (
    TranscriptionWarningValidation,
)


def test__warning_validation__retains_warning_subjects() -> None:
    assert issubclass(TranscriptionWarningValidation, AbstractValidation)
    assert {field.name for field in fields(TranscriptionWarningValidation)} >= {
        "document",
        "warnings",
        "valid_object_ids",
    }

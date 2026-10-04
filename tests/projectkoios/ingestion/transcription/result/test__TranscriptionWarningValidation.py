from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.result.warning_validation import (
    TranscriptionWarningValidation,
)


def test__warning_validation__retains_warning_count() -> None:
    validation = TranscriptionWarningValidation(
        result_id="structured-transcription-result:test",
        validated_warning_count=2,
    )

    assert isinstance(validation, AbstractValidation)
    assert validation.validated_warning_count == 2

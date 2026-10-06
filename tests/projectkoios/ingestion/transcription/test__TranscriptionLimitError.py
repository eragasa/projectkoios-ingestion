from projectkoios.ingestion.transcription.limits.error import (
    TranscriptionLimitError,
)


def test__transcription_limit_error__is_value_error() -> None:
    assert issubclass(TranscriptionLimitError, ValueError)

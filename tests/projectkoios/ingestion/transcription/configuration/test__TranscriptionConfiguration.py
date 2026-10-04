from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.configuration.configuration import (
    TranscriptionConfiguration,
)


def test__transcription_configuration__inherits_bounds_owner() -> None:
    value = TranscriptionConfiguration()
    assert isinstance(value, AbstractTranscriptionDataObject)
    assert value.max_result_bytes == value.MAX_RESULT_BYTES

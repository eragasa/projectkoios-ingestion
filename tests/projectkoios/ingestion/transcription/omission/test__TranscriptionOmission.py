from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.omission.omission import (
    TranscriptionOmission,
)


def test__transcription_omission__has_nominal_data_object_role() -> None:
    assert issubclass(TranscriptionOmission, AbstractTranscriptionDataObject)

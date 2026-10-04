from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.item import TranscriptionItem


def test__transcription_item__has_nominal_data_object_role() -> None:
    assert issubclass(TranscriptionItem, AbstractTranscriptionDataObject)

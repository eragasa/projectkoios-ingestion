from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.structured_request import (
    StructuredTranscriptionRequest,
)


def test__structured_transcription_request__has_concrete_action_role() -> None:
    assert issubclass(StructuredTranscriptionRequest, DataObjectActionRequest)
    assert issubclass(
        StructuredTranscriptionRequest, AbstractTranscriptionDataObject
    )

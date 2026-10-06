from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.result.structured import (
    StructuredTranscriptionResult,
)


def test__structured_transcription_result__has_concrete_action_role() -> None:
    assert issubclass(StructuredTranscriptionResult, DataObjectActionResult)
    assert issubclass(
        StructuredTranscriptionResult, AbstractTranscriptionDataObject
    )

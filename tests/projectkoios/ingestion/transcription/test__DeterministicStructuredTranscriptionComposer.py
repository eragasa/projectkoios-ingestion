from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.transcription.composer import (
    DeterministicStructuredTranscriptionComposer,
)


def test__deterministic_structured_transcription_composer__is_actionizer() -> (
    None
):
    assert isinstance(
        DeterministicStructuredTranscriptionComposer(), DataObjectActionizer
    )

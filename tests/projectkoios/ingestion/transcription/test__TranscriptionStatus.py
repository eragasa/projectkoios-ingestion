from projectkoios.ingestion.transcription.status.result import (
    TranscriptionStatus,
)


def test__transcription_status__never_implies_acceptance() -> None:
    assert {value.value for value in TranscriptionStatus} == {
        "proposed",
        "proposed_with_uncertainty",
    }

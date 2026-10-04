from projectkoios.ingestion.transcription.result_status import (
    TranscriptionStatus,
)


def test__transcription_status__never_implies_acceptance() -> None:
    assert {value.value for value in TranscriptionStatus} == {
        "proposed",
        "proposed_with_uncertainty",
    }

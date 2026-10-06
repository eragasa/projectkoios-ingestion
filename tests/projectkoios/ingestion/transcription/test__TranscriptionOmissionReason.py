from projectkoios.ingestion.transcription.reason.omission import (
    TranscriptionOmissionReason,
)


def test__transcription_omission_reason__names_explicit_coverage() -> None:
    assert "represented_by_typed_object" in {
        value.value for value in TranscriptionOmissionReason
    }

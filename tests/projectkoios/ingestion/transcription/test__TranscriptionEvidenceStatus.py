from projectkoios.ingestion.transcription.status.evidence import (
    TranscriptionEvidenceStatus,
)


def test__transcription_evidence_status__distinguishes_ambiguity() -> None:
    assert TranscriptionEvidenceStatus.AMBIGUOUS.value == "ambiguous"

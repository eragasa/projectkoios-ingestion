from projectkoios.ingestion.transcription.evidence.status import (
    TranscriptionEvidenceStatus,
)


def test__transcription_evidence_status__distinguishes_ambiguity() -> None:
    assert TranscriptionEvidenceStatus.AMBIGUOUS.value == "ambiguous"

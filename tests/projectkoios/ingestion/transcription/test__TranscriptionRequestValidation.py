from dataclasses import fields

from projectkoios.ingestion.base.validation import AbstractValidation
from projectkoios.ingestion.transcription.validation.request import (
    TranscriptionRequestValidation,
)


def test__transcription_request_validation__retains_compact_evidence() -> None:
    assert issubclass(TranscriptionRequestValidation, AbstractValidation)
    names = {field.name for field in fields(TranscriptionRequestValidation)}
    assert "document" not in names
    assert "structure_analysis" not in names
    assert names >= {
        "validation_id",
        "document_id",
        "structure_analysis_id",
        "artifact_inventory_id",
        "validated_artifact_bytes",
    }

from dataclasses import fields

from projectkoios.ingestion.base.validation import AbstractValidation
from projectkoios.ingestion.transcription.result_validation import (
    TranscriptionResultValidation,
)


def test__transcription_result_validation__retains_compact_evidence() -> None:
    assert issubclass(TranscriptionResultValidation, AbstractValidation)
    names = {field.name for field in fields(TranscriptionResultValidation)}
    assert "items" not in names
    assert "transcription_input" not in names
    assert names >= {
        "validation_id",
        "result_id",
        "request_id",
        "item_set_id",
        "omission_set_id",
        "warning_set_id",
        "validated_source_span_count",
        "validated_text_characters",
    }

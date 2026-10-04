from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.result.limit_validation import (
    TranscriptionResultLimitValidation,
)


def test__result_limit_validation__retains_bounded_counts() -> None:
    validation = TranscriptionResultLimitValidation(
        result_id="structured-transcription-result:test",
        validated_item_count=3,
        validated_source_span_count=5,
    )

    assert isinstance(validation, AbstractValidation)
    assert validation.validated_source_span_count == 5

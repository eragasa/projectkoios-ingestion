from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.result.object_validation import (
    TranscriptionResultObjectValidation,
)


def test__result_object_validation__retains_coverage_counts() -> None:
    validation = TranscriptionResultObjectValidation(
        result_id="structured-transcription-result:test",
        validated_item_count=4,
        validated_omission_count=1,
    )

    assert isinstance(validation, AbstractValidation)
    assert validation.validated_item_count == 4
    assert validation.validated_omission_count == 1

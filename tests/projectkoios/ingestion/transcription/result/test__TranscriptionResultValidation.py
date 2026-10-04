from dataclasses import FrozenInstanceError

import pytest
from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.result.validation import (
    TranscriptionResultValidation,
)


def test__transcription_result_validation__retains_completed_checks() -> None:
    validation = TranscriptionResultValidation(
        result_id="structured-transcription-result:test",
        validated_item_count=3,
        validated_omission_count=1,
        validated_warning_count=2,
    )

    assert isinstance(validation, AbstractValidation)
    assert validation.validated_warning_count == 2
    with pytest.raises(FrozenInstanceError):
        validation.validated_warning_count = 3  # type: ignore[misc]

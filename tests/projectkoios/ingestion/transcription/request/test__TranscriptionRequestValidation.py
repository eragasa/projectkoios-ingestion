from dataclasses import FrozenInstanceError

import pytest
from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.request.validation import (
    TranscriptionRequestValidation,
)


def test__transcription_request_validation__retains_completed_checks() -> None:
    validation = TranscriptionRequestValidation(
        document_id="document:test",
        validated_block_count=3,
        validated_node_count=2,
        validated_typed_object_count=1,
        validated_artifact_bytes=64,
    )

    assert isinstance(validation, AbstractValidation)
    assert validation.validated_block_count == 3
    with pytest.raises(FrozenInstanceError):
        validation.validated_block_count = 4  # type: ignore[misc]

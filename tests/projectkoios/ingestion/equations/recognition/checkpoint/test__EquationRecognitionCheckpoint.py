import pytest
from projectkoios.ingestion.equations.recognition.checkpoint.checkpoint import (
    EquationRecognitionCheckpoint,
)
from projectkoios.ingestion.equations.recognition.checkpoint.state import (
    EquationRecognitionWorkState,
)


def test__recognition_checkpoint__requires_and_preserves_failure_evidence() -> (
    None
):
    with pytest.raises(ValueError, match="requires an error"):
        EquationRecognitionCheckpoint(EquationRecognitionWorkState.FAILED)
    with pytest.raises(ValueError, match="cannot have an error"):
        EquationRecognitionCheckpoint(
            EquationRecognitionWorkState.PENDING,
            error="must not be erased",
        )

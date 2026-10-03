from __future__ import annotations

from projectkoios.ingestion.equations.recognition.error import (
    EquationRecognitionError,
)


def test__equation_recognition_error__is_a_concrete_runtime_failure() -> None:
    error = EquationRecognitionError("bounded recognition failure")

    assert isinstance(error, RuntimeError)
    assert str(error) == "bounded recognition failure"

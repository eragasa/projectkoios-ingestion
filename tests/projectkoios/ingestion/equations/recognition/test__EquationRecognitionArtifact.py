from __future__ import annotations

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.equations.recognition.artifact import (
    EquationRecognitionArtifact,
)


def test__equation_recognition_artifact__is_action_result() -> None:
    assert issubclass(EquationRecognitionArtifact, DataObjectActionResult)
    assert issubclass(EquationRecognitionArtifact, AbstractImmutableDataObject)

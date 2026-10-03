"""Nominal vendor-neutral equation-recognizer boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.equations.recognition.artifact import (
    EquationRecognitionArtifact,
)
from projectkoios.ingestion.equations.recognition.processor.identity import (
    EquationRecognitionProcessorIdentity,
)
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)


class AbstractEquationRecognizer(
    DataObjectActionizer[
        EquationRecognitionRequest,
        EquationRecognitionArtifact,
    ],
    ABC,
):
    """Vendor-neutral action boundary for equation recognition."""

    __slots__ = ()

    @property
    @abstractmethod
    def identity(self) -> EquationRecognitionProcessorIdentity:
        """Return the exact processor identity targeted by requests."""

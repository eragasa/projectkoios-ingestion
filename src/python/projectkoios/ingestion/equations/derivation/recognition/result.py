"""Successful equation-recognition derivation result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.equations.derivation.recognition.trace import (
    build_equation_recognition_success_trace,
)
from projectkoios.ingestion.equations.derivation.trace import (
    EquationDerivationTrace,
)
from projectkoios.ingestion.equations.recognition.artifact import (
    EquationRecognitionArtifact,
)
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class EquationRecognitionDerivationResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Correlated recognition artifact and its complete workflow trace."""

    CONTRACT_NAME: ClassVar[str] = "equation-recognition-derivation-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    derivation_id: str
    request: EquationRecognitionRequest
    recognition: EquationRecognitionArtifact
    trace: EquationDerivationTrace

    @classmethod
    def create(
        cls,
        *,
        request: EquationRecognitionRequest,
        recognition: EquationRecognitionArtifact,
    ) -> EquationRecognitionDerivationResult:
        trace = build_equation_recognition_success_trace(
            request=request,
            recognition=recognition,
        )
        return cls(
            derivation_id=stable_id(
                "equation-recognition-derivation-result",
                cls.CONTRACT_VERSION,
                request.request_id,
                recognition.artifact_id,
                trace.trace_id,
            ),
            request=request,
            recognition=recognition,
            trace=trace,
        )

    def __post_init__(self) -> None:
        if type(self.request) is not EquationRecognitionRequest:
            raise TypeError("request must be an EquationRecognitionRequest")
        if type(self.recognition) is not EquationRecognitionArtifact:
            raise TypeError(
                "recognition must be an EquationRecognitionArtifact"
            )
        if type(self.trace) is not EquationDerivationTrace:
            raise TypeError("trace must be an EquationDerivationTrace")
        expected_trace = build_equation_recognition_success_trace(
            request=self.request,
            recognition=self.recognition,
        )
        if self.trace != expected_trace:
            raise ValueError("recognition derivation trace is inconsistent")
        expected_id = stable_id(
            "equation-recognition-derivation-result",
            self.CONTRACT_VERSION,
            self.request.request_id,
            self.recognition.artifact_id,
            self.trace.trace_id,
        )
        if self.derivation_id != expected_id:
            raise ValueError("recognition derivation result ID is inconsistent")

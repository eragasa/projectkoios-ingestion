"""Failed equation-recognition derivation result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.equations.derivation.recognition.trace import (
    build_equation_recognition_failure_trace,
)
from projectkoios.ingestion.equations.derivation.trace import (
    EquationDerivationTrace,
)
from projectkoios.ingestion.equations.recognition.error import (
    EquationRecognitionError,
)
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class EquationRecognitionDerivationFailure(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Correlated exceptional failure and its non-consuming trace."""

    CONTRACT_NAME: ClassVar[str] = "equation-recognition-derivation-failure"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    failure_id: str
    request: EquationRecognitionRequest
    failure_type: str
    failure_message: str
    trace: EquationDerivationTrace

    @classmethod
    def create(
        cls,
        *,
        request: EquationRecognitionRequest,
        error: EquationRecognitionError,
    ) -> EquationRecognitionDerivationFailure:
        if not isinstance(error, EquationRecognitionError):
            raise TypeError("error must be an EquationRecognitionError")
        failure_type = type(error).__name__
        failure_message = str(error)
        trace = build_equation_recognition_failure_trace(
            request=request,
            failure_type=failure_type,
            failure_message=failure_message,
        )
        return cls(
            failure_id=stable_id(
                "equation-recognition-derivation-failure",
                cls.CONTRACT_VERSION,
                request.request_id,
                failure_type,
                failure_message,
                trace.trace_id,
            ),
            request=request,
            failure_type=failure_type,
            failure_message=failure_message,
            trace=trace,
        )

    def __post_init__(self) -> None:
        if type(self.request) is not EquationRecognitionRequest:
            raise TypeError("request must be an EquationRecognitionRequest")
        if type(self.failure_type) is not str or not self.failure_type:
            raise ValueError("recognition failure type is invalid")
        if type(self.failure_message) is not str or not self.failure_message:
            raise ValueError("recognition failure message is invalid")
        if type(self.trace) is not EquationDerivationTrace:
            raise TypeError("trace must be an EquationDerivationTrace")
        expected_trace = build_equation_recognition_failure_trace(
            request=self.request,
            failure_type=self.failure_type,
            failure_message=self.failure_message,
        )
        if self.trace != expected_trace:
            raise ValueError("recognition failure trace is inconsistent")
        expected_id = stable_id(
            "equation-recognition-derivation-failure",
            self.CONTRACT_VERSION,
            self.request.request_id,
            self.failure_type,
            self.failure_message,
            self.trace.trace_id,
        )
        if self.failure_id != expected_id:
            raise ValueError(
                "recognition derivation failure ID is inconsistent"
            )

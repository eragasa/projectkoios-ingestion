"""Engine-neutral equation-recognition workflow."""

from __future__ import annotations

from projectkoios.ingestion.equations.assembly.result import (
    EquationAssemblyResult,
)
from projectkoios.ingestion.equations.derivation.recognition.failure import (
    EquationRecognitionDerivationFailure,
)
from projectkoios.ingestion.equations.derivation.recognition.result import (
    EquationRecognitionDerivationResult,
)
from projectkoios.ingestion.equations.recognition.artifact import (
    EquationRecognitionArtifact,
)
from projectkoios.ingestion.equations.recognition.base import (
    AbstractEquationRecognizer,
)
from projectkoios.ingestion.equations.recognition.error import (
    EquationRecognitionError,
)
from projectkoios.ingestion.equations.recognition.processor.identity import (
    EquationRecognitionProcessorIdentity,
)
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)


class EquationRecognitionWorkflowError(RuntimeError):
    """Raised when workflow evidence cannot be correlated exactly."""


class EquationRecognitionWorkflowFailure(EquationRecognitionError):
    """Operational failure carrying its exact non-consuming trace."""

    def __init__(self, failure: EquationRecognitionDerivationFailure) -> None:
        if type(failure) is not EquationRecognitionDerivationFailure:
            raise TypeError(
                "failure must be an EquationRecognitionDerivationFailure"
            )
        self.failure = failure
        super().__init__(failure.failure_message)


def plan_equation_recognition(
    *,
    assembly: EquationAssemblyResult,
    processor: EquationRecognitionProcessorIdentity,
) -> EquationRecognitionRequest:
    """Project one immutable external-effect request from workflow state."""

    if type(assembly) is not EquationAssemblyResult:
        raise TypeError("assembly must be an EquationAssemblyResult")
    if type(processor) is not EquationRecognitionProcessorIdentity:
        raise TypeError(
            "processor must be an EquationRecognitionProcessorIdentity"
        )
    return EquationRecognitionRequest.create(
        assembly_artifact=assembly,
        processor_identity=processor,
    )


def record_equation_recognition_result(
    *,
    request: EquationRecognitionRequest,
    result: EquationRecognitionArtifact,
) -> EquationRecognitionArtifact:
    """Accept only the external result correlated to the exact request."""

    if type(request) is not EquationRecognitionRequest:
        raise TypeError("request must be an EquationRecognitionRequest")
    if type(result) is not EquationRecognitionArtifact:
        raise TypeError("result must be an EquationRecognitionArtifact")
    if result.request_id != request.request_id:
        raise EquationRecognitionWorkflowError(
            "recognition result does not match its workflow request"
        )
    return result


def record_equation_recognition_derivation(
    *,
    request: EquationRecognitionRequest,
    result: EquationRecognitionArtifact,
) -> EquationRecognitionDerivationResult:
    """Correlate one success and derive its exact transition trace."""

    correlated = record_equation_recognition_result(
        request=request,
        result=result,
    )
    return EquationRecognitionDerivationResult.create(
        request=request,
        recognition=correlated,
    )


def record_equation_recognition_failure(
    *,
    request: EquationRecognitionRequest,
    error: EquationRecognitionError,
) -> EquationRecognitionDerivationFailure:
    """Correlate one exceptional effect failure without consuming input."""

    if type(request) is not EquationRecognitionRequest:
        raise TypeError("request must be an EquationRecognitionRequest")
    if not isinstance(error, EquationRecognitionError):
        raise TypeError("error must be an EquationRecognitionError")
    return EquationRecognitionDerivationFailure.create(
        request=request,
        error=error,
    )


def execute_equation_recognition_derivation(
    *,
    recognizer: AbstractEquationRecognizer,
    assembly: EquationAssemblyResult,
) -> EquationRecognitionDerivationResult:
    """Execute recognition and return its correlated derivation trace."""

    if not isinstance(recognizer, AbstractEquationRecognizer):
        raise TypeError("recognizer must be an AbstractEquationRecognizer")
    request = plan_equation_recognition(
        assembly=assembly,
        processor=recognizer.identity,
    )
    try:
        result = recognizer.action(request=request)
    except EquationRecognitionError as error:
        failure = record_equation_recognition_failure(
            request=request,
            error=error,
        )
        raise EquationRecognitionWorkflowFailure(failure) from error
    return record_equation_recognition_derivation(
        request=request,
        result=result,
    )


def execute_equation_recognition(
    *,
    recognizer: AbstractEquationRecognizer,
    assembly: EquationAssemblyResult,
) -> EquationRecognitionArtifact:
    """Execute recognition while preserving the legacy artifact result API."""

    return execute_equation_recognition_derivation(
        recognizer=recognizer,
        assembly=assembly,
    ).recognition

"""Engine-neutral equation-recognition workflow."""

from __future__ import annotations

from projectkoios.ingestion.equation_enrichment import (
    AbstractEquationRecognizer,
    EquationAssemblyArtifact,
    EquationRecognitionArtifact,
    EquationRecognitionProcessorIdentity,
    EquationRecognitionRequest,
)


class EquationRecognitionWorkflowError(RuntimeError):
    """Raised when workflow evidence cannot be correlated exactly."""


def plan_equation_recognition(
    *,
    assembly: EquationAssemblyArtifact,
    processor: EquationRecognitionProcessorIdentity,
) -> EquationRecognitionRequest:
    """Project one immutable external-effect request from workflow state."""

    if type(assembly) is not EquationAssemblyArtifact:
        raise TypeError("assembly must be an EquationAssemblyArtifact")
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


def execute_equation_recognition(
    *,
    recognizer: AbstractEquationRecognizer,
    assembly: EquationAssemblyArtifact,
) -> EquationRecognitionArtifact:
    """Execute the workflow's requested vendor-neutral recognition effect."""

    if not isinstance(recognizer, AbstractEquationRecognizer):
        raise TypeError("recognizer must be an AbstractEquationRecognizer")
    request = plan_equation_recognition(
        assembly=assembly,
        processor=recognizer.identity,
    )
    result = recognizer.action(request=request)
    return record_equation_recognition_result(
        request=request,
        result=result,
    )

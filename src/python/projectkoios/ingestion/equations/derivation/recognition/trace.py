"""Deterministic derivation traces for equation-recognition effects."""

from __future__ import annotations

from projectkoios.ingestion.equations.derivation.trace import (
    EquationDerivationTrace,
)
from projectkoios.ingestion.equations.derivation.transition import (
    EquationDerivationTransition,
)
from projectkoios.ingestion.equations.recognition.artifact import (
    EquationRecognitionArtifact,
)
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)
from projectkoios.ingestion.identity import stable_id

EQUATION_RECOGNITION_DERIVATION_VERSION = "1.0"


def equation_recognition_configuration_identity(
    request: EquationRecognitionRequest,
) -> str:
    """Identify only the explicit recognition configuration choices."""

    if type(request) is not EquationRecognitionRequest:
        raise TypeError("request must be an EquationRecognitionRequest")
    return stable_id(
        "equation-recognition-configuration",
        EQUATION_RECOGNITION_DERIVATION_VERSION,
        request.processor_identity.temperature,
    )


def build_equation_recognition_success_trace(
    *,
    request: EquationRecognitionRequest,
    recognition: EquationRecognitionArtifact,
) -> EquationDerivationTrace:
    """Build the exact assembly-to-recognition artifact transition."""

    if type(request) is not EquationRecognitionRequest:
        raise TypeError("request must be an EquationRecognitionRequest")
    if type(recognition) is not EquationRecognitionArtifact:
        raise TypeError("recognition must be an EquationRecognitionArtifact")
    if recognition.request_id != request.request_id:
        raise ValueError("recognition does not match its derivation request")
    warning_codes = tuple(
        dict.fromkeys(
            warning
            for proposal in recognition.proposals
            for warning in proposal.warning_codes
        )
    )
    root_id = request.assembly_artifact.artifact_id
    transition = EquationDerivationTransition.succeeded(
        sequence=1,
        operation_name="equation-recognition",
        operation_version=EQUATION_RECOGNITION_DERIVATION_VERSION,
        input_ids=(root_id,),
        output_ids=(recognition.artifact_id,),
        request_id=request.request_id,
        result_id=recognition.artifact_id,
        processor_identity=request.processor_identity.identity_digest,
        configuration_identity=equation_recognition_configuration_identity(
            request
        ),
        warning_codes=warning_codes,
    )
    return EquationDerivationTrace(
        root_equation_ids=(root_id,),
        transitions=(transition,),
    )


def build_equation_recognition_failure_trace(
    *,
    request: EquationRecognitionRequest,
    failure_type: str,
    failure_message: str,
) -> EquationDerivationTrace:
    """Build a failed transition that retains the exact assembly root."""

    if type(request) is not EquationRecognitionRequest:
        raise TypeError("request must be an EquationRecognitionRequest")
    root_id = request.assembly_artifact.artifact_id
    transition = EquationDerivationTransition.failed(
        sequence=1,
        operation_name="equation-recognition",
        operation_version=EQUATION_RECOGNITION_DERIVATION_VERSION,
        input_ids=(root_id,),
        request_id=request.request_id,
        processor_identity=request.processor_identity.identity_digest,
        configuration_identity=equation_recognition_configuration_identity(
            request
        ),
        failure_type=failure_type,
        failure_message=failure_message,
    )
    return EquationDerivationTrace(
        root_equation_ids=(root_id,),
        transitions=(transition,),
    )

"""Deterministic derivation traces for equation-recognition effects."""

from __future__ import annotations

from projectkoios.ingestion.equations.derivation.recognition.operation import (
    EquationRecognitionDerivationOperation,
)
from projectkoios.ingestion.equations.derivation.trace import (
    EquationDerivationTrace,
)
from projectkoios.ingestion.equations.derivation.transition import (
    EquationDerivationTransition,
)
from projectkoios.ingestion.equations.image.base import AbstractEquationImage
from projectkoios.ingestion.equations.image.factory import EquationImage
from projectkoios.ingestion.equations.recognition.artifact import (
    EquationRecognitionArtifact,
)
from projectkoios.ingestion.equations.recognition.proposal import (
    EquationRecognitionProposal,
)
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)
from projectkoios.ingestion.equations.recognition.status import (
    EquationRecognitionStatus,
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
    """Build exact image-to-LaTeX-to-MathML representation transitions."""

    if type(request) is not EquationRecognitionRequest:
        raise TypeError("request must be an EquationRecognitionRequest")
    if type(recognition) is not EquationRecognitionArtifact:
        raise TypeError("recognition must be an EquationRecognitionArtifact")
    if recognition.request_id != request.request_id:
        raise ValueError("recognition does not match its derivation request")
    assemblies = request.assembly_artifact.assemblies
    expected_assembly_ids = tuple(item.assembly_id for item in assemblies)
    observed_assembly_ids = tuple(
        proposal.assembly_id for proposal in recognition.proposals
    )
    if observed_assembly_ids != expected_assembly_ids:
        raise ValueError(
            "recognition proposals do not exactly cover request assemblies"
        )
    images = _equation_images(request)
    transitions: list[EquationDerivationTransition] = []
    for image, proposal in zip(images, recognition.proposals, strict=True):
        _append_proposal_transitions(
            transitions=transitions,
            image=image,
            proposal=proposal,
            request=request,
        )
    return EquationDerivationTrace(
        root_equation_ids=tuple(image.equation_id for image in images),
        transitions=tuple(transitions),
    )


def build_equation_recognition_failure_trace(
    *,
    request: EquationRecognitionRequest,
    failure_type: str,
    failure_message: str,
) -> EquationDerivationTrace:
    """Build a failed transition retaining every exact input image."""

    if type(request) is not EquationRecognitionRequest:
        raise TypeError("request must be an EquationRecognitionRequest")
    images = _equation_images(request)
    root_ids = tuple(image.equation_id for image in images)
    transitions = (
        (
            EquationDerivationTransition.failed(
                sequence=1,
                operation_name=(
                    EquationRecognitionDerivationOperation.RECOGNITION.value
                ),
                operation_version=EQUATION_RECOGNITION_DERIVATION_VERSION,
                input_ids=root_ids,
                request_id=request.request_id,
                processor_identity=(request.processor_identity.identity_digest),
                configuration_identity=(
                    equation_recognition_configuration_identity(request)
                ),
                failure_type=failure_type,
                failure_message=failure_message,
            ),
        )
        if root_ids
        else ()
    )
    return EquationDerivationTrace(
        root_equation_ids=root_ids,
        transitions=transitions,
    )


def _equation_images(
    request: EquationRecognitionRequest,
) -> tuple[AbstractEquationImage, ...]:
    return tuple(
        EquationImage.from_bytes(
            content=assembly.rendered_region.content,
            source_ids=(assembly.rendered_region.region_id,),
        )
        for assembly in request.assembly_artifact.assemblies
    )


def _append_proposal_transitions(
    *,
    transitions: list[EquationDerivationTransition],
    image: AbstractEquationImage,
    proposal: EquationRecognitionProposal,
    request: EquationRecognitionRequest,
) -> None:
    if proposal.status is EquationRecognitionStatus.NOT_REQUESTED:
        return
    sequence = len(transitions) + 1
    configuration_identity = equation_recognition_configuration_identity(
        request
    )
    if proposal.status is EquationRecognitionStatus.FAILED:
        if proposal.failure_message is None:
            raise ValueError("failed proposal has no failure evidence")
        transitions.append(
            EquationDerivationTransition.failed(
                sequence=sequence,
                operation_name=(
                    EquationRecognitionDerivationOperation.RECOGNITION.value
                ),
                operation_version=EQUATION_RECOGNITION_DERIVATION_VERSION,
                input_ids=(image.equation_id,),
                request_id=request.request_id,
                processor_identity=(request.processor_identity.identity_digest),
                configuration_identity=configuration_identity,
                failure_type="EquationRecognitionProposalFailure",
                failure_message=proposal.failure_message,
                warning_codes=proposal.warning_codes,
            )
        )
        return
    if proposal.status is not EquationRecognitionStatus.PROPOSED:
        raise TypeError("recognition proposal status is invalid")
    if proposal.latex is None:
        raise ValueError("proposed recognition has no LaTeX representation")
    if proposal.latex.equation_source_ids != (image.equation_id,):
        raise ValueError(
            "recognized LaTeX does not derive from the request image"
        )
    transitions.append(
        EquationDerivationTransition.succeeded(
            sequence=sequence,
            operation_name=(
                EquationRecognitionDerivationOperation.RECOGNITION.value
            ),
            operation_version=EQUATION_RECOGNITION_DERIVATION_VERSION,
            input_ids=(image.equation_id,),
            output_ids=(proposal.latex.equation_id,),
            request_id=request.request_id,
            result_id=proposal.proposal_id,
            processor_identity=request.processor_identity.identity_digest,
            configuration_identity=configuration_identity,
            warning_codes=proposal.warning_codes,
        )
    )
    if proposal.mathml is None:
        return
    if (
        proposal.mathml_processor_identity is None
        or proposal.mathml_processor_version is None
    ):
        raise ValueError("MathML proposal has no processor evidence")
    transitions.append(
        EquationDerivationTransition.succeeded(
            sequence=sequence + 1,
            operation_name=(
                EquationRecognitionDerivationOperation.MATHML_CONVERSION.value
            ),
            operation_version=proposal.mathml_processor_version,
            input_ids=(proposal.latex.equation_id,),
            output_ids=(proposal.mathml.equation_id,),
            request_id=stable_id(
                "equation-mathml-conversion-request",
                EQUATION_RECOGNITION_DERIVATION_VERSION,
                proposal.proposal_id,
                proposal.latex.equation_id,
            ),
            result_id=proposal.mathml.equation_id,
            processor_identity=proposal.mathml_processor_identity,
            configuration_identity=stable_id(
                "equation-mathml-conversion-configuration",
                EQUATION_RECOGNITION_DERIVATION_VERSION,
                "default",
            ),
        )
    )

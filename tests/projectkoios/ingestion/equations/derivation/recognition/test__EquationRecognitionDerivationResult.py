from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest
from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.equations.derivation.recognition.result import (
    EquationRecognitionDerivationResult,
)
from projectkoios.ingestion.equations.derivation.status import (
    EquationDerivationTransitionStatus,
)
from projectkoios.ingestion.equations.latex import EquationLatex
from projectkoios.ingestion.equations.mathml import EquationMathML
from projectkoios.ingestion.equations.recognition.identity import (
    EQUATION_RECOGNITION_CONTRACT_VERSION,
)
from projectkoios.ingestion.identity import stable_id

from tests.equation_recognition_derivation_support import artifact, request


def test__recognition_derivation_result__binds_success_trace() -> None:
    recognition_request = request()
    recognition = artifact(recognition_request=recognition_request)

    result = EquationRecognitionDerivationResult.create(
        request=recognition_request,
        recognition=recognition,
    )

    recognition_transition, mathml_transition = result.trace.transitions
    proposal = recognition.proposals[0]
    assert proposal.latex is not None
    assert proposal.mathml is not None
    assert isinstance(result, DataObjectActionResult)
    assert (
        recognition_transition.status
        is EquationDerivationTransitionStatus.SUCCEEDED
    )
    assert recognition_transition.input_ids == (
        proposal.latex.equation_source_ids[0],
    )
    assert recognition_transition.output_ids == (proposal.latex.equation_id,)
    assert recognition_transition.request_id == recognition_request.request_id
    assert recognition_transition.result_id == proposal.proposal_id
    assert mathml_transition.input_ids == (proposal.latex.equation_id,)
    assert mathml_transition.output_ids == (proposal.mathml.equation_id,)
    assert (
        mathml_transition.processor_identity
        == proposal.mathml_processor_identity
    )
    assert mathml_transition.operation_version == (
        proposal.mathml_processor_version
    )
    assert result.trace.final_equation_ids == (proposal.mathml.equation_id,)
    with pytest.raises(FrozenInstanceError):
        result.derivation_id = "changed"  # type: ignore[misc]


def test__recognition_derivation_result__requires_exact_proposal_coverage() -> (
    None
):
    recognition_request = request()
    recognition = artifact(recognition_request=recognition_request)
    recognition_without_proposals = replace(
        recognition,
        artifact_id=stable_id(
            "equation-recognition-artifact",
            EQUATION_RECOGNITION_CONTRACT_VERSION,
            recognition.assembly_artifact_id,
            recognition.processor_identity.identity_digest,
            (),
            recognition.invocation_exit_code,
            recognition.diagnostic_byte_size,
            recognition.diagnostic_sha256,
        ),
        proposals=(),
    )

    with pytest.raises(ValueError, match="exactly cover"):
        EquationRecognitionDerivationResult.create(
            request=recognition_request,
            recognition=recognition_without_proposals,
        )


def test__recognition_derivation_result__rejects_wrong_image_provenance() -> (
    None
):
    recognition_request = request()
    recognition = artifact(recognition_request=recognition_request)
    proposal = recognition.proposals[0]
    assert proposal.latex is not None
    assert proposal.mathml is not None
    wrong_latex = EquationLatex(
        source_ids=("equation-image:sha256:wrong",),
        latex=proposal.latex.latex,
    )
    wrong_mathml = EquationMathML(
        source_ids=(wrong_latex.equation_id,),
        mathml=proposal.mathml.mathml,
    )
    wrong_proposal = replace(
        proposal,
        latex=wrong_latex,
        mathml=wrong_mathml,
    )
    recognition_with_wrong_provenance = replace(
        recognition,
        proposals=(wrong_proposal,),
    )

    with pytest.raises(ValueError, match="request image"):
        EquationRecognitionDerivationResult.create(
            request=recognition_request,
            recognition=recognition_with_wrong_provenance,
        )


def test__recognition_derivation_result__rejects_altered_trace() -> None:
    recognition_request = request()
    result = EquationRecognitionDerivationResult.create(
        request=recognition_request,
        recognition=artifact(recognition_request=recognition_request),
    )
    altered = replace(
        result.trace.transitions[0],
        warning_codes=("altered",),
    )
    altered_trace = replace(result.trace, transitions=(altered,))

    with pytest.raises(ValueError, match="trace is inconsistent"):
        replace(result, trace=altered_trace)

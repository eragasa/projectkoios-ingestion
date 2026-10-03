from dataclasses import replace

import pytest
from projectkoios.ingestion.equations.latex import EquationLatex
from projectkoios.ingestion.equations.mathml import EquationMathML
from projectkoios.ingestion.equations.recognition.identity import (
    EQUATION_RECOGNITION_CONTRACT_VERSION,
)
from projectkoios.ingestion.equations.recognition.proposal import (
    EquationRecognitionProposal,
)
from projectkoios.ingestion.equations.recognition.status import (
    EquationRecognitionStatus,
)
from projectkoios.ingestion.identity import stable_id


def _proposal() -> EquationRecognitionProposal:
    latex = EquationLatex(
        source_ids=("equation-image:sha256:fixture",),
        latex=r"E=mc^2",
    )
    mathml = EquationMathML(
        source_ids=(latex.equation_id,),
        mathml="<math><mi>E</mi></math>",
    )
    warnings = ("recognition_confidence_unavailable",)
    proposal_id = stable_id(
        "equation-recognition-proposal",
        EQUATION_RECOGNITION_CONTRACT_VERSION,
        "assembly:fixture",
        EquationRecognitionStatus.PROPOSED,
        latex.latex,
        mathml.mathml,
        warnings,
        None,
        "processor:fixture",
    )
    return EquationRecognitionProposal(
        proposal_id=proposal_id,
        assembly_id="assembly:fixture",
        status=EquationRecognitionStatus.PROPOSED,
        latex=latex,
        mathml=mathml,
        mathml_processor_identity=stable_id(
            "equation-mathml-processor",
            "fixture",
            "1",
        ),
        mathml_processor_version="1",
        warning_codes=warnings,
        failure_message=None,
        processor_identity_digest="processor:fixture",
    )


def test__equation_recognition_proposal__owns_typed_representations() -> None:
    proposal = _proposal()

    assert isinstance(proposal.latex, EquationLatex)
    assert isinstance(proposal.mathml, EquationMathML)
    assert proposal.mathml.equation_source_ids == (proposal.latex.equation_id,)


def test__equation_recognition_proposal__preserves_legacy_stable_identity() -> (
    None
):
    proposal = _proposal()

    expected = stable_id(
        "equation-recognition-proposal",
        EQUATION_RECOGNITION_CONTRACT_VERSION,
        proposal.assembly_id,
        proposal.status,
        proposal.latex.latex,
        proposal.mathml.mathml,
        proposal.warning_codes,
        proposal.failure_message,
        proposal.processor_identity_digest,
    )
    assert proposal.proposal_id == expected


def test__equation_recognition_proposal__rejects_raw_latex_string() -> None:
    proposal = _proposal()

    with pytest.raises(ValueError, match="typed LaTeX"):
        replace(proposal, latex=r"E=mc^2")  # type: ignore[arg-type]


def test__equation_recognition_proposal__requires_mathml_processor() -> None:
    proposal = _proposal()

    with pytest.raises(ValueError, match="exact processor evidence"):
        replace(proposal, mathml_processor_identity=None)

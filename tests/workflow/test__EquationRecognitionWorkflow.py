from __future__ import annotations

import pytest
from projectkoios.ingestion.equations.derivation.recognition.result import (
    EquationRecognitionDerivationResult,
)
from projectkoios.ingestion.equations.image.factory import EquationImage
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

from tests.equation_recognition_derivation_support import (
    artifact,
    assembly,
    processor,
)
from workflow.equation_recognition import (
    EquationRecognitionWorkflowError,
    EquationRecognitionWorkflowFailure,
    execute_equation_recognition,
    execute_equation_recognition_derivation,
    plan_equation_recognition,
    record_equation_recognition_derivation,
)


class _SuccessfulRecognizer(AbstractEquationRecognizer):
    def __init__(self, identity: EquationRecognitionProcessorIdentity) -> None:
        self._identity = identity

    @property
    def identity(self) -> EquationRecognitionProcessorIdentity:
        return self._identity

    def action(
        self,
        *,
        request: EquationRecognitionRequest,
    ) -> EquationRecognitionArtifact:
        return artifact(recognition_request=request)


class _FailingRecognizer(_SuccessfulRecognizer):
    def action(
        self,
        *,
        request: EquationRecognitionRequest,
    ) -> EquationRecognitionArtifact:
        del request
        raise EquationRecognitionError("bounded recognition failure")


def test__equation_recognition_workflow__returns_correlated_success_trace() -> (
    None
):
    recognition_assembly = assembly()
    recognizer = _SuccessfulRecognizer(processor())

    derivation = execute_equation_recognition_derivation(
        recognizer=recognizer,
        assembly=recognition_assembly,
    )
    legacy = execute_equation_recognition(
        recognizer=recognizer,
        assembly=recognition_assembly,
    )

    assert isinstance(derivation, EquationRecognitionDerivationResult)
    assert derivation.recognition == legacy
    proposal = derivation.recognition.proposals[0]
    assert proposal.latex is not None
    assert proposal.mathml is not None
    assert derivation.trace.root_equation_ids == (
        proposal.latex.equation_source_ids[0],
    )
    assert derivation.trace.final_equation_ids == (proposal.mathml.equation_id,)


def test__equation_recognition_workflow__rejects_uncorrelated_result() -> None:
    recognition_request = plan_equation_recognition(
        assembly=assembly(name="expected"),
        processor=processor(name="expected"),
    )
    unrelated_request = plan_equation_recognition(
        assembly=assembly(name="unrelated"),
        processor=processor(name="unrelated"),
    )

    with pytest.raises(
        EquationRecognitionWorkflowError,
        match="does not match",
    ):
        record_equation_recognition_derivation(
            request=recognition_request,
            result=artifact(recognition_request=unrelated_request),
        )


def test__equation_recognition_workflow__raises_failure_with_trace() -> None:
    recognition_assembly = assembly()

    with pytest.raises(
        EquationRecognitionWorkflowFailure,
        match="bounded recognition failure",
    ) as raised:
        execute_equation_recognition_derivation(
            recognizer=_FailingRecognizer(processor()),
            assembly=recognition_assembly,
        )

    assert isinstance(raised.value, EquationRecognitionError)
    equation_assembly = recognition_assembly.assemblies[0]
    image = EquationImage.from_bytes(
        content=equation_assembly.rendered_region.content,
        source_ids=(equation_assembly.rendered_region.region_id,),
    )
    assert raised.value.failure.trace.root_equation_ids == (image.equation_id,)
    assert raised.value.failure.trace.final_equation_ids == (image.equation_id,)

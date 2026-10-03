from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.equations.derivation.recognition.failure import (
    EquationRecognitionDerivationFailure,
)
from projectkoios.ingestion.equations.derivation.status import (
    EquationDerivationTransitionStatus,
)
from projectkoios.ingestion.equations.image.factory import EquationImage
from projectkoios.ingestion.equations.recognition.error import (
    EquationRecognitionError,
)

from tests.equation_recognition_derivation_support import request


def test__recognition_derivation_failure__retains_input_and_error() -> None:
    recognition_request = request()

    failure = EquationRecognitionDerivationFailure.create(
        request=recognition_request,
        error=EquationRecognitionError("bounded recognition failure"),
    )

    transition = failure.trace.transitions[0]
    assembly = recognition_request.assembly_artifact.assemblies[0]
    image = EquationImage.from_bytes(
        content=assembly.rendered_region.content,
        source_ids=(assembly.rendered_region.region_id,),
    )
    assert isinstance(failure, DataObjectActionResult)
    assert transition.status is EquationDerivationTransitionStatus.FAILED
    assert transition.input_ids == (image.equation_id,)
    assert transition.output_ids == ()
    assert transition.request_id == recognition_request.request_id
    assert failure.trace.final_equation_ids == (image.equation_id,)
    assert failure.failure_type == "EquationRecognitionError"
    assert failure.failure_message == "bounded recognition failure"


def test__recognition_derivation_failure__rejects_altered_trace() -> None:
    failure = EquationRecognitionDerivationFailure.create(
        request=request(),
        error=EquationRecognitionError("bounded recognition failure"),
    )
    altered_transition = replace(
        failure.trace.transitions[0],
        failure_message="different failure",
    )
    altered_trace = replace(
        failure.trace,
        transitions=(altered_transition,),
    )

    with pytest.raises(ValueError, match="trace is inconsistent"):
        replace(failure, trace=altered_trace)

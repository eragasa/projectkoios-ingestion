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

from tests.equation_recognition_derivation_support import artifact, request


def test__recognition_derivation_result__binds_success_trace() -> None:
    recognition_request = request()
    recognition = artifact(recognition_request=recognition_request)

    result = EquationRecognitionDerivationResult.create(
        request=recognition_request,
        recognition=recognition,
    )

    transition = result.trace.transitions[0]
    assert isinstance(result, DataObjectActionResult)
    assert transition.status is EquationDerivationTransitionStatus.SUCCEEDED
    assert transition.input_ids == (
        recognition_request.assembly_artifact.artifact_id,
    )
    assert transition.output_ids == (recognition.artifact_id,)
    assert transition.request_id == recognition_request.request_id
    assert transition.result_id == recognition.artifact_id
    assert result.trace.final_equation_ids == (recognition.artifact_id,)
    with pytest.raises(FrozenInstanceError):
        result.derivation_id = "changed"  # type: ignore[misc]


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

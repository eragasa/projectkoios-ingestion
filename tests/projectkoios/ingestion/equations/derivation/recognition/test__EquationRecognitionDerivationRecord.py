from copy import deepcopy
from dataclasses import replace

import pytest
from projectkoios.ingestion.equations.derivation.recognition.record import (
    EquationRecognitionDerivationRecord,
)
from projectkoios.ingestion.equations.derivation.recognition.result import (
    EquationRecognitionDerivationResult,
)
from projectkoios.ingestion.serialization import contract_dict

from tests.equation_recognition_derivation_support import artifact, request


def test__recognition_derivation_record__retains_compact_correlation() -> None:
    recognition_request = request()
    recognition = artifact(recognition_request=recognition_request)
    result = EquationRecognitionDerivationResult.create(
        request=recognition_request,
        recognition=recognition,
    )

    record = EquationRecognitionDerivationRecord.create(result)

    assert record.request_id == recognition_request.request_id
    assert record.recognition_artifact_id == recognition.artifact_id
    assert record.trace == result.trace
    with pytest.raises(ValueError, match="record ID is inconsistent"):
        replace(record, record_id="invalid")


def test__recognition_derivation_record__rehydrates_typed_trace() -> None:
    recognition_request = request()
    recognition = artifact(recognition_request=recognition_request)
    result = EquationRecognitionDerivationResult.create(
        request=recognition_request,
        recognition=recognition,
    )
    record = EquationRecognitionDerivationRecord.create(result)
    serialized = contract_dict(record)

    assert EquationRecognitionDerivationRecord.from_dict(serialized) == record

    changed = deepcopy(serialized)
    trace = changed["trace"]
    assert isinstance(trace, dict)
    transitions = trace["transitions"]
    assert isinstance(transitions, list)
    transition = transitions[0]
    assert isinstance(transition, dict)
    transition["transition_id"] = "equation-derivation-transition:changed"
    with pytest.raises(ValueError, match="transition ID is inconsistent"):
        EquationRecognitionDerivationRecord.from_dict(changed)

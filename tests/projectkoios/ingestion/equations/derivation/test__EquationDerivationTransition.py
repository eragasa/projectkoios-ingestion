from __future__ import annotations

import pytest
from projectkoios.ingestion.equations.derivation.status import (
    EquationDerivationTransitionStatus,
)
from projectkoios.ingestion.equations.derivation.transition import (
    EquationDerivationTransition,
)


def test__equation_derivation_transition__retains_success_evidence() -> None:
    transition = EquationDerivationTransition.succeeded(
        sequence=1,
        operation_name="equation-recognition",
        operation_version="1.0",
        input_ids=("equation-image:one",),
        output_ids=("equation-latex:one",),
        request_id="recognition-request:one",
        result_id="recognition-result:one",
        processor_identity="processor:one",
        configuration_identity="configuration:one",
        warning_codes=("recognition_confidence_unavailable",),
    )

    assert transition.status is EquationDerivationTransitionStatus.SUCCEEDED
    assert transition.transition_id.startswith(
        "equation-derivation-transition:sha256:"
    )


def test__derivation_transition__retains_failure_without_output() -> None:
    transition = EquationDerivationTransition.failed(
        sequence=1,
        operation_name="equation-recognition",
        operation_version="1.0",
        input_ids=("equation-image:one",),
        request_id="recognition-request:one",
        processor_identity="processor:one",
        configuration_identity="configuration:one",
        failure_type="EquationRecognitionError",
        failure_message="bounded recognition failure",
    )

    assert transition.status is EquationDerivationTransitionStatus.FAILED
    assert transition.output_ids == ()
    assert transition.result_id is None


def test__derivation_transition__rejects_success_without_output() -> None:
    with pytest.raises(ValueError, match="output IDs"):
        EquationDerivationTransition.succeeded(
            sequence=1,
            operation_name="equation-recognition",
            operation_version="1.0",
            input_ids=("equation-image:one",),
            output_ids=(),
            request_id="recognition-request:one",
            result_id="recognition-result:one",
            processor_identity="processor:one",
            configuration_identity="configuration:one",
        )

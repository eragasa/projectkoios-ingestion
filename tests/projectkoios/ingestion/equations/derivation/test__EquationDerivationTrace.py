from __future__ import annotations

import pytest
from projectkoios.ingestion.equations.derivation.trace import (
    EquationDerivationTrace,
)
from projectkoios.ingestion.equations.derivation.transition import (
    EquationDerivationTransition,
)


def _success(
    *,
    sequence: int,
    input_id: str,
    output_id: str,
) -> EquationDerivationTransition:
    return EquationDerivationTransition.succeeded(
        sequence=sequence,
        operation_name=f"operation-{sequence}",
        operation_version="1.0",
        input_ids=(input_id,),
        output_ids=(output_id,),
        request_id=f"request:{sequence}",
        result_id=f"result:{sequence}",
        processor_identity=f"processor:{sequence}",
        configuration_identity=f"configuration:{sequence}",
    )


def test__equation_derivation_trace__allows_empty_derivation() -> None:
    trace = EquationDerivationTrace(
        root_equation_ids=(),
        transitions=(),
    )

    assert trace.final_equation_ids == ()


def test__equation_derivation_trace__retains_ordered_causal_chain() -> None:
    trace = EquationDerivationTrace(
        root_equation_ids=("equation-image:one",),
        transitions=(
            _success(
                sequence=1,
                input_id="equation-image:one",
                output_id="equation-latex:one",
            ),
            _success(
                sequence=2,
                input_id="equation-latex:one",
                output_id="equation-mathml:one",
            ),
        ),
    )

    assert trace.final_equation_ids == ("equation-mathml:one",)
    assert trace.trace_id.startswith("equation-derivation-trace:sha256:")


def test__equation_derivation_trace__retains_input_after_failure() -> None:
    failure = EquationDerivationTransition.failed(
        sequence=1,
        operation_name="equation-recognition",
        operation_version="1.0",
        input_ids=("equation-image:one",),
        request_id="request:one",
        processor_identity="processor:one",
        configuration_identity="configuration:one",
        failure_type="EquationRecognitionError",
        failure_message="bounded failure",
    )
    trace = EquationDerivationTrace(
        root_equation_ids=("equation-image:one",),
        transitions=(failure,),
    )

    assert trace.final_equation_ids == ("equation-image:one",)


def test__equation_derivation_trace__rejects_unknown_input() -> None:
    with pytest.raises(ValueError, match="unknown input"):
        EquationDerivationTrace(
            root_equation_ids=("equation-image:one",),
            transitions=(
                _success(
                    sequence=1,
                    input_id="equation-image:other",
                    output_id="equation-latex:one",
                ),
            ),
        )

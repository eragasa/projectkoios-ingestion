from projectkoios.ingestion.equations.derivation.status import (
    EquationDerivationTransitionStatus,
)


def test__equation_derivation_transition_status__has_terminal_values() -> None:
    assert EquationDerivationTransitionStatus.SUCCEEDED == "succeeded"
    assert EquationDerivationTransitionStatus.FAILED == "failed"

"""Deterministic equation-recognition checkpoint transitions."""

from projectkoios.ingestion.equations.recognition.checkpoint.checkpoint import (
    EquationRecognitionCheckpoint,
)
from projectkoios.ingestion.equations.recognition.checkpoint.deferral import (
    EquationRecognitionDeferral,
)
from projectkoios.ingestion.equations.recognition.checkpoint.state import (
    EquationRecognitionWorkState,
)


def defer_equation_recognition(
    checkpoint: EquationRecognitionCheckpoint,
) -> EquationRecognitionDeferral:
    """Defer only untouched pending work and preserve every other state."""

    resulting_state = (
        EquationRecognitionWorkState.NOT_REQUESTED
        if checkpoint.state is EquationRecognitionWorkState.PENDING
        else checkpoint.state
    )
    return EquationRecognitionDeferral(
        previous_state=checkpoint.state,
        resulting_state=resulting_state,
        preserved_error=checkpoint.error,
        changed=checkpoint.state is EquationRecognitionWorkState.PENDING,
    )

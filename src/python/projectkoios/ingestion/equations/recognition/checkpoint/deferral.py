"""Equation-recognition deferral result."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.equations.recognition.checkpoint.state import (
    EquationRecognitionWorkState,
)


@dataclass(frozen=True)
class EquationRecognitionDeferral:
    """Exact state transition produced by a recognition deferral."""

    previous_state: EquationRecognitionWorkState
    resulting_state: EquationRecognitionWorkState
    preserved_error: str | None
    changed: bool

    def __post_init__(self) -> None:
        expected_state = (
            EquationRecognitionWorkState.NOT_REQUESTED
            if self.previous_state is EquationRecognitionWorkState.PENDING
            else self.previous_state
        )
        if self.resulting_state is not expected_state:
            raise ValueError("recognition deferral transition is inconsistent")
        if self.changed is not (
            self.previous_state is EquationRecognitionWorkState.PENDING
        ):
            raise ValueError("recognition deferral change flag is inconsistent")
        if self.previous_state is EquationRecognitionWorkState.FAILED:
            if self.preserved_error is None or not self.preserved_error.strip():
                raise ValueError(
                    "recognition failure evidence was not preserved"
                )
        elif self.preserved_error is not None:
            raise ValueError("recognition deferral has an unexpected error")

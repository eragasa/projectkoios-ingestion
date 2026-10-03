"""Equation-recognition checkpoint contract."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.equations.recognition.checkpoint.state import (
    EquationRecognitionWorkState,
)


@dataclass(frozen=True)
class EquationRecognitionCheckpoint:
    """One immutable recognition work checkpoint."""

    state: EquationRecognitionWorkState
    error: str | None = None

    def __post_init__(self) -> None:
        if self.state is EquationRecognitionWorkState.FAILED:
            if self.error is None or not self.error.strip():
                raise ValueError(
                    "failed recognition checkpoint requires an error"
                )
        elif self.error is not None:
            raise ValueError(
                "non-failed recognition checkpoint cannot have an error"
            )

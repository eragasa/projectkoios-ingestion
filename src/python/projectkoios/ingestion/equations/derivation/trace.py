"""Complete ordered equation derivation trace."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.equations.derivation.status import (
    EquationDerivationTransitionStatus,
)
from projectkoios.ingestion.equations.derivation.transition import (
    EquationDerivationTransition,
)
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class EquationDerivationTrace(AbstractImmutableDataObject):
    """Causally closed ordered transitions from exact root representations."""

    CONTRACT_NAME: ClassVar[str] = "equation-derivation-trace"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAX_ROOT_IDS: ClassVar[int] = 256
    MAX_TRANSITIONS: ClassVar[int] = 4_096
    MAX_ID_CHARACTERS: ClassVar[int] = 4_096

    root_equation_ids: tuple[str, ...]
    transitions: tuple[EquationDerivationTransition, ...]
    trace_id: str = field(init=False)
    final_equation_ids: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        self._validate_root_ids()
        if type(self.transitions) is not tuple:
            raise TypeError("equation derivation transitions must be a tuple")
        if len(self.transitions) > self.MAX_TRANSITIONS:
            raise ValueError(
                "equation derivation transition count is out of bounds"
            )
        if any(
            type(transition) is not EquationDerivationTransition
            for transition in self.transitions
        ):
            raise TypeError("equation derivation transitions must be typed")
        transition_ids = tuple(
            transition.transition_id for transition in self.transitions
        )
        if len(transition_ids) != len(set(transition_ids)):
            raise ValueError("equation derivation transitions must be unique")
        available = list(self.root_equation_ids)
        known = set(available)
        for expected_sequence, transition in enumerate(
            self.transitions,
            start=1,
        ):
            if transition.sequence != expected_sequence:
                raise ValueError(
                    "equation derivation transition sequence is discontinuous"
                )
            if not set(transition.input_ids).issubset(known):
                raise ValueError(
                    "equation derivation transition has an unknown input"
                )
            if set(transition.output_ids) & known:
                raise ValueError(
                    "equation derivation output identity was already observed"
                )
            if (
                transition.status
                is EquationDerivationTransitionStatus.SUCCEEDED
            ):
                consumed = set(transition.input_ids)
                available = [
                    identity
                    for identity in available
                    if identity not in consumed
                ]
                available.extend(transition.output_ids)
                known.update(transition.output_ids)
        object.__setattr__(self, "final_equation_ids", tuple(available))
        object.__setattr__(
            self,
            "trace_id",
            stable_id(
                "equation-derivation-trace",
                self.CONTRACT_VERSION,
                self.root_equation_ids,
                transition_ids,
                tuple(available),
            ),
        )

    def _validate_root_ids(self) -> None:
        if type(self.root_equation_ids) is not tuple:
            raise TypeError("equation derivation root IDs must be a tuple")
        if len(self.root_equation_ids) > self.MAX_ROOT_IDS or len(
            self.root_equation_ids
        ) != len(set(self.root_equation_ids)):
            raise ValueError("equation derivation root IDs are invalid")
        if any(
            type(value) is not str
            or not value
            or value != value.strip()
            or len(value) > self.MAX_ID_CHARACTERS
            for value in self.root_equation_ids
        ):
            raise ValueError("equation derivation root IDs are invalid")

"""Exact LaTeX equation representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.equations.base import AbstractEquation
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class EquationLatex(AbstractEquation):
    """One exact LaTeX representation without acceptance semantics."""

    CONTRACT_NAME: ClassVar[str] = "equation-latex"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAX_CHARACTERS: ClassVar[int] = 65_536

    source_ids: tuple[str, ...]
    latex: str
    _equation_id: str = field(init=False, repr=False)

    @property
    def equation_id(self) -> str:
        return self._equation_id

    @property
    def equation_source_ids(self) -> tuple[str, ...]:
        return self.source_ids

    def __post_init__(self) -> None:
        self._validate_source_ids(self.source_ids)
        if type(self.latex) is not str:
            raise TypeError("equation LaTeX must be a string")
        if not self.latex.strip() or len(self.latex) > self.MAX_CHARACTERS:
            raise ValueError("equation LaTeX size is out of bounds")
        object.__setattr__(
            self,
            "_equation_id",
            stable_id(
                "equation-latex",
                self.CONTRACT_VERSION,
                self.source_ids,
                self.latex,
            ),
        )

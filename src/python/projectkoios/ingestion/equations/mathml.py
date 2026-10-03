"""Exact MathML equation representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar
from xml.etree import ElementTree

from projectkoios.ingestion.equations.base import AbstractEquation
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class EquationMathML(AbstractEquation):
    """One exact bounded well-formed MathML representation."""

    CONTRACT_NAME: ClassVar[str] = "equation-mathml"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAX_UTF8_BYTES: ClassVar[int] = 2_000_000

    source_ids: tuple[str, ...]
    mathml: str
    _equation_id: str = field(init=False, repr=False)

    @property
    def equation_id(self) -> str:
        return self._equation_id

    @property
    def equation_source_ids(self) -> tuple[str, ...]:
        return self.source_ids

    def __post_init__(self) -> None:
        self._validate_source_ids(self.source_ids)
        if type(self.mathml) is not str:
            raise TypeError("equation MathML must be a string")
        encoded = self.mathml.encode("utf-8")
        if not self.mathml.strip() or len(encoded) > self.MAX_UTF8_BYTES:
            raise ValueError("equation MathML size is out of bounds")
        lowered = self.mathml.lower()
        if "<!doctype" in lowered or "<!entity" in lowered:
            raise ValueError("equation MathML contains forbidden declarations")
        try:
            root = ElementTree.fromstring(self.mathml)
        except ElementTree.ParseError as error:
            raise ValueError("equation MathML is not well formed") from error
        local_name = root.tag.rsplit("}", 1)[-1]
        if local_name != "math":
            raise ValueError("equation MathML root must be math")
        object.__setattr__(
            self,
            "_equation_id",
            stable_id(
                "equation-mathml",
                self.CONTRACT_VERSION,
                self.source_ids,
                self.mathml,
            ),
        )

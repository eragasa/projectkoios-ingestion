"""Exact KaTeX-rendered equation representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.equations.base import AbstractEquation
from projectkoios.ingestion.equations.latex import EquationLatex
from projectkoios.ingestion.equations.mathml import EquationMathML
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


@dataclass(frozen=True, slots=True)
class EquationKatex(AbstractEquation):
    """KaTeX HTML/MathML output bound to its exact LaTeX input."""

    CONTRACT_NAME: ClassVar[str] = "equation-katex"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAX_HTML_UTF8_BYTES: ClassVar[int] = 4_000_000
    MAX_VERSION_CHARACTERS: ClassVar[int] = 256

    latex: EquationLatex
    mathml: EquationMathML
    html: str
    katex_version: str
    _equation_id: str = field(init=False, repr=False)
    _html_sha256: str = field(init=False, repr=False)

    @property
    def equation_id(self) -> str:
        return self._equation_id

    @property
    def equation_source_ids(self) -> tuple[str, ...]:
        return (self.latex.equation_id, self.mathml.equation_id)

    @property
    def html_sha256(self) -> str:
        return self._html_sha256

    def __post_init__(self) -> None:
        if type(self.latex) is not EquationLatex:
            raise TypeError("KaTeX input must be an EquationLatex")
        if type(self.mathml) is not EquationMathML:
            raise TypeError("KaTeX MathML must be an EquationMathML")
        if self.latex.equation_id not in self.mathml.equation_source_ids:
            raise ValueError("KaTeX MathML does not derive from its LaTeX")
        if type(self.html) is not str:
            raise TypeError("KaTeX HTML must be a string")
        encoded = self.html.encode("utf-8")
        if not self.html.strip() or len(encoded) > self.MAX_HTML_UTF8_BYTES:
            raise ValueError("KaTeX HTML size is out of bounds")
        if (
            type(self.katex_version) is not str
            or not self.katex_version
            or self.katex_version != self.katex_version.strip()
            or len(self.katex_version) > self.MAX_VERSION_CHARACTERS
        ):
            raise ValueError("KaTeX version is invalid")
        digest = SHA256Fingerprinter.fingerprint(content=encoded)
        object.__setattr__(self, "_html_sha256", digest)
        object.__setattr__(
            self,
            "_equation_id",
            stable_id(
                "equation-katex",
                self.CONTRACT_VERSION,
                self.latex.equation_id,
                self.mathml.equation_id,
                self.katex_version,
                digest,
                len(encoded),
            ),
        )

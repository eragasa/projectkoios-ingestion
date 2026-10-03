"""One retained output from a successful Pix2Tex invocation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base import AbstractImmutableDataObject


@dataclass(frozen=True, slots=True)
class Pix2TexInvocationOutput(AbstractImmutableDataObject):
    """Exact bounded LaTeX correlated to one assembly."""

    CONTRACT_NAME: ClassVar[str] = "pix2tex-invocation-output"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAX_LATEX_CHARACTERS: ClassVar[int] = 16_384

    assembly_id: str
    latex: str

    def __post_init__(self) -> None:
        if not self.assembly_id or not self.latex.strip():
            raise ValueError("Pix2Tex invocation output is incomplete")
        if len(self.latex) > self.MAX_LATEX_CHARACTERS:
            raise ValueError("Pix2Tex invocation output exceeds its limit")

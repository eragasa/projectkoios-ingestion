"""Successful whole-process Pix2Tex invocation result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.integrations.pix2tex.invocation.output import (
    Pix2TexInvocationOutput,
)


@dataclass(frozen=True, slots=True)
class Pix2TexInvocationResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Bounded diagnostic bytes and correlated successful outputs."""

    CONTRACT_NAME: ClassVar[str] = "pix2tex-invocation-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAX_DIAGNOSTIC_BYTES: ClassVar[int] = 4_000_000

    diagnostic: bytes
    outputs: tuple[Pix2TexInvocationOutput, ...]

    def __post_init__(self) -> None:
        if type(self.diagnostic) is not bytes:
            raise TypeError("Pix2Tex invocation diagnostic must be bytes")
        if len(self.diagnostic) > self.MAX_DIAGNOSTIC_BYTES:
            raise ValueError("Pix2Tex invocation diagnostic exceeds its limit")
        if type(self.outputs) is not tuple or any(
            type(output) is not Pix2TexInvocationOutput
            for output in self.outputs
        ):
            raise TypeError("Pix2Tex invocation outputs must be typed")
        output_ids = tuple(output.assembly_id for output in self.outputs)
        if len(output_ids) != len(set(output_ids)):
            raise ValueError("Pix2Tex invocation outputs must be unique")

"""One exact Pix2Tex subprocess invocation request."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.equations.assembly.model import EquationAssembly


@dataclass(frozen=True, slots=True)
class Pix2TexInvocationRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Typed assembly images selected for one Pix2Tex process."""

    CONTRACT_NAME: ClassVar[str] = "pix2tex-invocation-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    assemblies: tuple[EquationAssembly, ...]

    def __post_init__(self) -> None:
        if not self.assemblies or any(
            type(assembly) is not EquationAssembly
            for assembly in self.assemblies
        ):
            raise ValueError(
                "Pix2Tex invocation requires typed equation assemblies"
            )
        assembly_ids = tuple(
            assembly.assembly_id for assembly in self.assemblies
        )
        if len(assembly_ids) != len(set(assembly_ids)):
            raise ValueError("Pix2Tex invocation assemblies must be unique")

"""Bounded equation-assembly result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.equations.assembly.identity import (
    EQUATION_ASSEMBLY_CONTRACT_VERSION,
)
from projectkoios.ingestion.equations.assembly.model import EquationAssembly
from projectkoios.ingestion.identity import stable_id

_MAX_ASSEMBLIES = 256


@dataclass(frozen=True, slots=True)
class EquationAssemblyResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """All deterministic equation assemblies for one detection result."""

    CONTRACT_NAME: ClassVar[str] = "equation-assembly-result"
    CONTRACT_VERSION: ClassVar[str] = EQUATION_ASSEMBLY_CONTRACT_VERSION

    artifact_id: str
    source_id: str
    source_content_hash: str
    document_id: str
    detection_result_id: str
    assemblies: tuple[EquationAssembly, ...]
    contract_version: str = EQUATION_ASSEMBLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_ASSEMBLY_CONTRACT_VERSION:
            raise ValueError("unsupported equation assembly result version")
        if len(self.assemblies) > _MAX_ASSEMBLIES:
            raise ValueError("equation assembly count exceeds the limit")
        ids = tuple(item.assembly_id for item in self.assemblies)
        if len(ids) != len(set(ids)):
            raise ValueError("equation assembly IDs must be unique")
        expected = stable_id(
            "equation-assembly-artifact",
            EQUATION_ASSEMBLY_CONTRACT_VERSION,
            self.source_id,
            self.source_content_hash,
            self.document_id,
            self.detection_result_id,
            ids,
        )
        if self.artifact_id != expected:
            raise ValueError("equation assembly result ID is inconsistent")

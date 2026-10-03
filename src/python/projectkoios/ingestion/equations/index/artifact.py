"""Bounded equation index artifact."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.equations.index.identity import (
    EQUATION_INDEX_CONTRACT_VERSION,
)
from projectkoios.ingestion.equations.index.record import EquationIndexRecord
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True)
class EquationIndexArtifact:
    """Compact equation records derived from assembly and recognition."""

    artifact_id: str
    source_id: str
    source_content_hash: str
    assembly_artifact_id: str
    recognition_artifact_id: str
    records: tuple[EquationIndexRecord, ...]
    contract_version: str = EQUATION_INDEX_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_INDEX_CONTRACT_VERSION:
            raise ValueError("unsupported equation index artifact version")
        ids = tuple(item.record_id for item in self.records)
        if len(ids) != len(set(ids)):
            raise ValueError("equation index record IDs must be unique")
        expected = stable_id(
            "equation-index-artifact",
            EQUATION_INDEX_CONTRACT_VERSION,
            self.source_id,
            self.source_content_hash,
            self.assembly_artifact_id,
            self.recognition_artifact_id,
            ids,
        )
        if self.artifact_id != expected:
            raise ValueError("equation index artifact ID is inconsistent")

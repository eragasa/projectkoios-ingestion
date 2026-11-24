"""One source-bound conflict observation for table acceptance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.tables.acceptance.conflict import (
    TableEvidenceConflictKind,
)
from projectkoios.ingestion.tables.acceptance.validation import (
    require_decimal_text,
    require_id,
    require_sha256,
    require_text,
)


@dataclass(frozen=True, slots=True)
class TableEvidenceConflictObservation(AbstractImmutableDataObject):
    """Bind one observed disagreement to its immutable source and cell."""

    CONTRACT_NAME: ClassVar[str] = "table-evidence-conflict-observation"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    kind: TableEvidenceConflictKind
    observation_sha256: str
    cell_id: str
    observed_text: str
    proposed_text: str
    observation_id: str = field(init=False)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported conflict-observation contract")
        if not isinstance(self.kind, TableEvidenceConflictKind):
            raise TypeError("kind must be TableEvidenceConflictKind")
        require_sha256("observation_sha256", self.observation_sha256)
        require_id("cell_id", self.cell_id, "table-evidence-proposal-cell")
        require_text("observed_text", self.observed_text)
        require_decimal_text("proposed_text", self.proposed_text)
        object.__setattr__(
            self,
            "observation_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.kind,
                self.observation_sha256,
                self.cell_id,
                self.observed_text,
                self.proposed_text,
            ),
        )
        require_id("observation_id", self.observation_id, self.CONTRACT_NAME)

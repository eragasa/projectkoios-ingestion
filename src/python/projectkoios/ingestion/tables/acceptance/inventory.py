"""Complete source-bound conflict inventory for one table decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.tables.acceptance.conflict import (
    TableEvidenceConflictKind,
)
from projectkoios.ingestion.tables.acceptance.observation import (
    TableEvidenceConflictObservation,
)
from projectkoios.ingestion.tables.acceptance.validation import (
    require_id,
    require_index,
    require_sha256,
)


@dataclass(frozen=True, slots=True)
class TableEvidenceConflictInventory(AbstractImmutableDataObject):
    """Declare exact conflict closure derived from immutable observations."""

    CONTRACT_NAME: ClassVar[str] = "table-evidence-conflict-inventory"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    machine_checklist_sha256: str
    external_notebook_cross_check_sha256: str
    native_extraction_conflict_count: int
    independent_ocr_conflict_count: int
    external_notebook_conflict_count: int
    observations: tuple[TableEvidenceConflictObservation, ...]
    inventory_id: str = field(init=False)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported conflict-inventory contract")
        require_sha256(
            "machine_checklist_sha256", self.machine_checklist_sha256
        )
        require_sha256(
            "external_notebook_cross_check_sha256",
            self.external_notebook_cross_check_sha256,
        )
        for name, value in (
            (
                "native_extraction_conflict_count",
                self.native_extraction_conflict_count,
            ),
            (
                "independent_ocr_conflict_count",
                self.independent_ocr_conflict_count,
            ),
            (
                "external_notebook_conflict_count",
                self.external_notebook_conflict_count,
            ),
        ):
            require_index(name, value, maximum=65_536)
        if not isinstance(self.observations, tuple) or not self.observations:
            raise ValueError("observations must be a non-empty immutable tuple")
        if any(
            type(item) is not TableEvidenceConflictObservation
            for item in self.observations
        ):
            raise TypeError("observations contain an unsupported value")
        keys = tuple((item.kind, item.cell_id) for item in self.observations)
        if len(set(keys)) != len(keys):
            raise ValueError("observations must be unique by kind and cell")
        counts = {
            kind: sum(item.kind is kind for item in self.observations)
            for kind in TableEvidenceConflictKind
        }
        if counts != {
            TableEvidenceConflictKind.NATIVE_EXTRACTION: (
                self.native_extraction_conflict_count
            ),
            TableEvidenceConflictKind.INDEPENDENT_OCR: (
                self.independent_ocr_conflict_count
            ),
            TableEvidenceConflictKind.EXTERNAL_NOTEBOOK: (
                self.external_notebook_conflict_count
            ),
        }:
            raise ValueError("conflict counts disagree with observations")
        for item in self.observations:
            expected_sha = (
                self.external_notebook_cross_check_sha256
                if item.kind is TableEvidenceConflictKind.EXTERNAL_NOTEBOOK
                else self.machine_checklist_sha256
            )
            if item.observation_sha256 != expected_sha:
                raise ValueError(
                    "conflict observation source identity is inconsistent"
                )
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.machine_checklist_sha256,
                self.external_notebook_cross_check_sha256,
                self.native_extraction_conflict_count,
                self.independent_ocr_conflict_count,
                self.external_notebook_conflict_count,
                tuple(item.observation_id for item in self.observations),
            ),
        )
        require_id("inventory_id", self.inventory_id, self.CONTRACT_NAME)

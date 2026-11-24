"""Explicit disposition of one proposal conflict observation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.tables.acceptance.validation import (
    require_decimal_text,
    require_id,
    require_sha256,
    require_text,
)


class TableEvidenceConflictKind(StrEnum):
    """Closed origins of observations conflicting with an accepted proposal."""

    NATIVE_EXTRACTION = "native_extraction"
    INDEPENDENT_OCR = "independent_ocr"
    EXTERNAL_NOTEBOOK = "external_notebook"


class TableEvidenceConflictResolution(StrEnum):
    """Closed resolution for this exact acceptance contract."""

    ACCEPT_EXACT_PROPOSAL_VALUE = "accept_exact_proposal_value"


@dataclass(frozen=True, slots=True)
class TableEvidenceConflictDisposition(AbstractImmutableDataObject):
    """Bind one conflicting observed value to the selected proposal cell."""

    CONTRACT_NAME: ClassVar[str] = "table-evidence-conflict-disposition"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    kind: TableEvidenceConflictKind
    observation_sha256: str
    cell_id: str
    observed_text: str
    accepted_text: str
    resolution: TableEvidenceConflictResolution
    disposition_id: str = field(init=False)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported conflict-disposition contract")
        if not isinstance(self.kind, TableEvidenceConflictKind):
            raise TypeError("kind must be TableEvidenceConflictKind")
        require_sha256("observation_sha256", self.observation_sha256)
        require_id("cell_id", self.cell_id, "table-evidence-proposal-cell")
        require_text("observed_text", self.observed_text)
        require_decimal_text("accepted_text", self.accepted_text)
        if self.resolution is not (
            TableEvidenceConflictResolution.ACCEPT_EXACT_PROPOSAL_VALUE
        ):
            raise ValueError(
                "conflict resolution must select the proposal value"
            )
        object.__setattr__(
            self,
            "disposition_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.kind,
                self.observation_sha256,
                self.cell_id,
                self.observed_text,
                self.accepted_text,
                self.resolution,
            ),
        )

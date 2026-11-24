"""Accepted table evidence derived from proposal plus explicit decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.tables.acceptance.conflict import (
    TableEvidenceConflictKind,
)
from projectkoios.ingestion.tables.acceptance.decision import (
    TableEvidenceHumanAcceptanceDecision,
)
from projectkoios.ingestion.tables.acceptance.inventory import (
    TableEvidenceConflictInventory,
)
from projectkoios.ingestion.tables.acceptance.proposal import (
    TableEvidenceProposal,
)
from projectkoios.ingestion.tables.acceptance.validation import (
    require_id,
    require_positive,
)


class AcceptedTableEvidenceStatus(StrEnum):
    """Closed lifecycle state of this additive acceptance result."""

    ACCEPTED = "accepted"


@dataclass(frozen=True, slots=True)
class AcceptedTableEvidenceResult(AbstractImmutableDataObject):
    """Bind complete table values to explicit human acceptance evidence."""

    CONTRACT_NAME: ClassVar[str] = "accepted-table-evidence-result"
    CONTRACT_VERSION: ClassVar[str] = "1.1"

    proposal: TableEvidenceProposal
    conflict_inventory: TableEvidenceConflictInventory
    decision: TableEvidenceHumanAcceptanceDecision
    status: AcceptedTableEvidenceStatus
    compound_count: int
    parameter_count: int
    numeric_cell_count: int
    result_id: str = field(init=False)
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        proposal: TableEvidenceProposal,
        conflict_inventory: TableEvidenceConflictInventory,
        decision: TableEvidenceHumanAcceptanceDecision,
    ) -> AcceptedTableEvidenceResult:
        return cls(
            proposal=proposal,
            conflict_inventory=conflict_inventory,
            decision=decision,
            status=AcceptedTableEvidenceStatus.ACCEPTED,
            compound_count=len(proposal.rows),
            parameter_count=len(proposal.parameters),
            numeric_cell_count=proposal.cell_count,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported accepted-table-evidence contract")
        if type(self.proposal) is not TableEvidenceProposal:
            raise TypeError("proposal must be TableEvidenceProposal")
        if type(self.conflict_inventory) is not TableEvidenceConflictInventory:
            raise TypeError(
                "conflict_inventory must be TableEvidenceConflictInventory"
            )
        if type(self.decision) is not TableEvidenceHumanAcceptanceDecision:
            raise TypeError(
                "decision must be TableEvidenceHumanAcceptanceDecision"
            )
        if self.status is not AcceptedTableEvidenceStatus.ACCEPTED:
            raise ValueError(
                "accepted table evidence must have accepted status"
            )
        require_positive("compound_count", self.compound_count, maximum=512)
        require_positive("parameter_count", self.parameter_count, maximum=128)
        require_positive(
            "numeric_cell_count", self.numeric_cell_count, maximum=65_536
        )
        if (
            self.compound_count != len(self.proposal.rows)
            or self.parameter_count != len(self.proposal.parameters)
            or self.numeric_cell_count != self.proposal.cell_count
            or self.numeric_cell_count
            != self.compound_count * self.parameter_count
        ):
            raise ValueError("accepted table closure counts are inconsistent")
        if (
            self.decision.proposal_id != self.proposal.proposal_id
            or self.decision.proposal_sha256 != self.proposal.proposal_sha256
        ):
            raise ValueError("decision and proposal identities disagree")
        if (
            self.decision.conflict_inventory_id
            != self.conflict_inventory.inventory_id
            or self.decision.machine_checklist_sha256
            != self.conflict_inventory.machine_checklist_sha256
            or self.decision.external_notebook_cross_check_sha256
            != self.conflict_inventory.external_notebook_cross_check_sha256
        ):
            raise ValueError("decision and conflict inventory disagree")
        cells = {
            cell.cell_id: cell
            for row in self.proposal.rows
            for cell in row.cells
        }
        required_machine = set()
        for cell in cells.values():
            for flag in cell.ambiguity_flags:
                kind = (
                    TableEvidenceConflictKind.NATIVE_EXTRACTION
                    if flag == "native-render-disagreement"
                    else TableEvidenceConflictKind.INDEPENDENT_OCR
                )
                required_machine.add((kind, cell.cell_id))
        inventory_by_key = {
            (item.kind, item.cell_id): item
            for item in self.conflict_inventory.observations
        }
        inventory_machine = {
            key
            for key in inventory_by_key
            if key[0]
            in {
                TableEvidenceConflictKind.NATIVE_EXTRACTION,
                TableEvidenceConflictKind.INDEPENDENT_OCR,
            }
        }
        if inventory_machine != required_machine:
            raise ValueError(
                "inventory must contain every machine conflict exactly once"
            )
        for observation in self.conflict_inventory.observations:
            target_cell = cells.get(observation.cell_id)
            if target_cell is None:
                raise ValueError(
                    "conflict observation references an unknown cell"
                )
            if observation.proposed_text != target_cell.proposed_text:
                raise ValueError(
                    "conflict observation differs from the proposal value"
                )
            expected_observed_text = (
                target_cell.raw_native_text
                if observation.kind
                is TableEvidenceConflictKind.NATIVE_EXTRACTION
                else target_cell.independent_ocr_text
                if observation.kind is TableEvidenceConflictKind.INDEPENDENT_OCR
                else observation.observed_text
            )
            if observation.observed_text != expected_observed_text:
                raise ValueError(
                    "machine observation differs from preserved "
                    "proposal evidence"
                )
        dispositions_by_key = {
            (item.kind, item.cell_id): item
            for item in self.decision.conflict_dispositions
        }
        if dispositions_by_key.keys() != inventory_by_key.keys():
            raise ValueError(
                "decision must dispose every inventoried conflict exactly once"
            )
        for key, disposition in dispositions_by_key.items():
            observation = inventory_by_key[key]
            if (
                disposition.observation_sha256 != observation.observation_sha256
                or disposition.observed_text != observation.observed_text
                or disposition.accepted_text != observation.proposed_text
            ):
                raise ValueError(
                    "conflict disposition differs from its exact observation"
                )
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.proposal.proposal_id,
                self.conflict_inventory.inventory_id,
                self.decision.decision_id,
                self.status,
                self.compound_count,
                self.parameter_count,
                self.numeric_cell_count,
            ),
        )
        require_id("result_id", self.result_id, self.CONTRACT_NAME)

"""Append-only human acceptance decision for one exact table proposal."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.tables.acceptance.conflict import (
    TableEvidenceConflictDisposition,
    TableEvidenceConflictKind,
)
from projectkoios.ingestion.tables.acceptance.validation import (
    parse_utc_timestamp,
    require_id,
    require_sha256,
    require_string_tuple,
    require_text,
)

ACCEPTANCE_AUTHORITY_SCOPE = "ingestion_table_evidence_operator_acceptance_only"
EXCLUDED_AUTHORITIES = (
    "bibliographic_identity",
    "search_admission",
    "scientific_acceptance",
    "material_validation",
    "publication",
    "redistribution_rights",
    "equation_evidence",
    "claim_support",
)


@dataclass(frozen=True, slots=True)
class TableEvidenceHumanAcceptanceDecision(AbstractImmutableDataObject):
    """Record explicit acceptance without rewriting proposal observations."""

    CONTRACT_NAME: ClassVar[str] = "table-evidence-human-acceptance-decision"
    CONTRACT_VERSION: ClassVar[str] = "1.1"

    proposal_id: str
    proposal_sha256: str
    conflict_inventory_id: str
    machine_checklist_sha256: str
    external_notebook_cross_check_sha256: str
    actor_id: str
    verification_basis: str
    instruction_message_id: str
    instruction_observed_at_utc: str
    recorded_at_utc: str
    acceptance_basis: str
    authority_scope: str
    excluded_authorities: tuple[str, ...]
    conflict_dispositions: tuple[TableEvidenceConflictDisposition, ...]
    decision_id: str = field(init=False)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported table-evidence decision contract")
        require_id("proposal_id", self.proposal_id, "table-evidence-proposal")
        require_sha256("proposal_sha256", self.proposal_sha256)
        require_id(
            "conflict_inventory_id",
            self.conflict_inventory_id,
            "table-evidence-conflict-inventory",
        )
        require_sha256(
            "machine_checklist_sha256", self.machine_checklist_sha256
        )
        require_sha256(
            "external_notebook_cross_check_sha256",
            self.external_notebook_cross_check_sha256,
        )
        require_text("actor_id", self.actor_id, identity=True)
        require_text(
            "verification_basis", self.verification_basis, identity=True
        )
        require_text(
            "instruction_message_id", self.instruction_message_id, identity=True
        )
        instruction_time = parse_utc_timestamp(
            "instruction_observed_at_utc", self.instruction_observed_at_utc
        )
        recorded_time = parse_utc_timestamp(
            "recorded_at_utc", self.recorded_at_utc
        )
        if recorded_time < instruction_time:
            raise ValueError(
                "recorded_at_utc cannot precede instruction_observed_at_utc"
            )
        require_text("acceptance_basis", self.acceptance_basis)
        if self.authority_scope != ACCEPTANCE_AUTHORITY_SCOPE:
            raise ValueError("acceptance authority scope is unsupported")
        require_string_tuple(
            "excluded_authorities",
            self.excluded_authorities,
            unique=True,
            required=True,
        )
        if self.excluded_authorities != EXCLUDED_AUTHORITIES:
            raise ValueError(
                "excluded authorities must preserve the contract boundary"
            )
        if (
            not isinstance(self.conflict_dispositions, tuple)
            or not self.conflict_dispositions
        ):
            raise ValueError(
                "conflict dispositions must be a non-empty immutable tuple"
            )
        if any(
            type(item) is not TableEvidenceConflictDisposition
            for item in self.conflict_dispositions
        ):
            raise TypeError(
                "conflict dispositions contain an unsupported value"
            )
        keys = tuple(
            (item.kind, item.cell_id) for item in self.conflict_dispositions
        )
        if len(set(keys)) != len(keys):
            raise ValueError(
                "conflict dispositions must be unique by kind and cell"
            )
        for item in self.conflict_dispositions:
            expected_sha = (
                self.external_notebook_cross_check_sha256
                if item.kind is TableEvidenceConflictKind.EXTERNAL_NOTEBOOK
                else self.machine_checklist_sha256
            )
            if item.observation_sha256 != expected_sha:
                raise ValueError(
                    "conflict disposition observation identity is inconsistent"
                )
        object.__setattr__(
            self,
            "decision_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.proposal_id,
                self.proposal_sha256,
                self.conflict_inventory_id,
                self.machine_checklist_sha256,
                self.external_notebook_cross_check_sha256,
                self.actor_id,
                self.verification_basis,
                self.instruction_message_id,
                self.instruction_observed_at_utc,
                self.recorded_at_utc,
                self.acceptance_basis,
                self.authority_scope,
                self.excluded_authorities,
                tuple(
                    item.disposition_id for item in self.conflict_dispositions
                ),
            ),
        )

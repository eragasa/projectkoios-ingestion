"""Stable identity of one inventory implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.identity import AbstractIdentity
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class InventoryIdentity(AbstractIdentity):
    """Bind an inventory to target, configuration, evidence, and authority."""

    CONTRACT_NAME: ClassVar[str] = "inventory-identity"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    inventory_actionizer_id: str
    name: str
    version: str
    target_contract: str
    configuration_contract: str
    evidence_contract: str
    authority_requirement: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        name: str,
        version: str,
        target_contract: str,
        configuration_contract: str,
        evidence_contract: str,
        authority_requirement: str,
    ) -> InventoryIdentity:
        """Create one inventory implementation identity."""
        parts = (
            name,
            version,
            target_contract,
            configuration_contract,
            evidence_contract,
            authority_requirement,
        )
        return cls(
            inventory_actionizer_id=stable_id(
                "inventory-identity",
                cls.CONTRACT_VERSION,
                parts,
            ),
            name=name,
            version=version,
            target_contract=target_contract,
            configuration_contract=configuration_contract,
            evidence_contract=evidence_contract,
            authority_requirement=authority_requirement,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported inventory-identity contract")
        parts = (
            self.name,
            self.version,
            self.target_contract,
            self.configuration_contract,
            self.evidence_contract,
            self.authority_requirement,
        )
        if any(type(value) is not str or not value for value in parts):
            raise ValueError("inventory identity is incomplete")
        expected = stable_id(
            "inventory-identity",
            self.CONTRACT_VERSION,
            parts,
        )
        if self.inventory_actionizer_id != expected:
            raise ValueError("inventory identity is inconsistent")

"""Fixed result envelope for inventory observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.base.inventory.evidence import (
    AbstractInventoryEvidence,
)
from projectkoios.ingestion.base.inventory.identity.model import (
    InventoryIdentity,
)
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class InventoryResult[EvidenceT: AbstractInventoryEvidence](
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Bind observed evidence to request and inventory identities."""

    CONTRACT_NAME: ClassVar[str] = "inventory-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    request_id: str
    idempotency_key: str
    inventory: InventoryIdentity
    evidence: EvidenceT
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request_id: str,
        idempotency_key: str,
        inventory: InventoryIdentity,
        evidence: EvidenceT,
    ) -> InventoryResult[EvidenceT]:
        """Create one immutable successful observation result."""
        return cls(
            result_id=stable_id(
                "inventory-result",
                cls.CONTRACT_VERSION,
                request_id,
                idempotency_key,
                inventory.inventory_actionizer_id,
                evidence.inventory_id,
            ),
            request_id=request_id,
            idempotency_key=idempotency_key,
            inventory=inventory,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported inventory-result contract")
        if not isinstance(self.inventory, InventoryIdentity):
            raise TypeError("inventory result identity is invalid")
        if not isinstance(self.evidence, AbstractInventoryEvidence):
            raise TypeError("inventory result evidence is invalid")
        expected = stable_id(
            "inventory-result",
            self.CONTRACT_VERSION,
            self.request_id,
            self.idempotency_key,
            self.inventory.inventory_actionizer_id,
            self.evidence.inventory_id,
        )
        if self.result_id != expected:
            raise ValueError("inventory result ID is inconsistent")

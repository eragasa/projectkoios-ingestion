"""Request for extraction projection inventory equivalence verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.materialization.evidence import (
    ExtractionProjectionMaterializationEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.kind import (  # noqa: E501
    ExtractionProjectionEquivalenceKind,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.evidence import (  # noqa: E501
    ExtractionProjectionInventoryEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.expected import (  # noqa: E501
    ExpectedExtractionProjectionInventory,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionInventoryEquivalenceRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Bind one expected snapshot to one independently observed snapshot."""

    CONTRACT_NAME: ClassVar[str] = (
        "extraction-projection-inventory-equivalence-request"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    idempotency_key: str
    kind: ExtractionProjectionEquivalenceKind
    expected: ExpectedExtractionProjectionInventory
    observed: ExtractionProjectionInventoryEvidence
    replay_materialization: ExtractionProjectionMaterializationEvidence | None
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        kind: ExtractionProjectionEquivalenceKind,
        expected: ExpectedExtractionProjectionInventory,
        observed: ExtractionProjectionInventoryEvidence,
        replay_materialization: (
            ExtractionProjectionMaterializationEvidence | None
        ) = None,
    ) -> ExtractionProjectionInventoryEquivalenceRequest:
        """Create one deterministic evidence-comparison request."""
        values = (
            kind,
            expected.expected_inventory_id,
            observed.inventory_id,
            (
                replay_materialization.evidence_id
                if replay_materialization is not None
                else None
            ),
        )
        key = stable_id(
            "extraction-projection-inventory-equivalence-idempotency",
            cls.CONTRACT_VERSION,
            values,
        )
        return cls(
            request_id=stable_id(
                "extraction-projection-inventory-equivalence-request",
                cls.CONTRACT_VERSION,
                key,
            ),
            idempotency_key=key,
            kind=kind,
            expected=expected,
            observed=observed,
            replay_materialization=replay_materialization,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported inventory-equivalence request")
        if not isinstance(self.kind, ExtractionProjectionEquivalenceKind):
            raise TypeError("inventory-equivalence kind is invalid")
        if type(self.expected) is not ExpectedExtractionProjectionInventory:
            raise TypeError("expected inventory has the wrong contract")
        if type(self.observed) is not ExtractionProjectionInventoryEvidence:
            raise TypeError("observed inventory has the wrong contract")
        if self.kind is ExtractionProjectionEquivalenceKind.SAME_STORE_REPLAY:
            if (
                type(self.replay_materialization)
                is not ExtractionProjectionMaterializationEvidence
            ):
                raise TypeError("same-store replay evidence is required")
        elif self.replay_materialization is not None:
            raise ValueError("independent rebuild cannot bind replay evidence")
        values = (
            self.kind,
            self.expected.expected_inventory_id,
            self.observed.inventory_id,
            (
                self.replay_materialization.evidence_id
                if self.replay_materialization is not None
                else None
            ),
        )
        key = stable_id(
            "extraction-projection-inventory-equivalence-idempotency",
            self.CONTRACT_VERSION,
            values,
        )
        if self.idempotency_key != key:
            raise ValueError(
                "inventory-equivalence idempotency is inconsistent"
            )
        expected_request = stable_id(
            "extraction-projection-inventory-equivalence-request",
            self.CONTRACT_VERSION,
            key,
        )
        if self.request_id != expected_request:
            raise ValueError("inventory-equivalence request ID is inconsistent")

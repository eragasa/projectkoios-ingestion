"""Result of extraction projection inventory equivalence verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.actions.status import (
    ExtractionActionStatus,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.kind import (  # noqa: E501
    ExtractionProjectionEquivalenceKind,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.mismatch import (  # noqa: E501
    ExtractionProjectionInventoryMismatch,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.request import (  # noqa: E501
    ExtractionProjectionInventoryEquivalenceRequest,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionInventoryEquivalenceResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Report a completed comparison separately from its equivalence outcome."""

    CONTRACT_NAME: ClassVar[str] = (
        "extraction-projection-inventory-equivalence-result"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    request_id: str
    idempotency_key: str
    status: ExtractionActionStatus
    disposition: ExtractionActionDisposition
    kind: ExtractionProjectionEquivalenceKind
    expected_inventory_id: str
    observed_inventory_id: str
    replay_materialization_inventory_id: str | None
    equivalent: bool
    mismatches: tuple[ExtractionProjectionInventoryMismatch, ...]
    mismatched_collection_names: tuple[str, ...]
    verifier_name: str
    verifier_version: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: ExtractionProjectionInventoryEquivalenceRequest,
        mismatches: tuple[ExtractionProjectionInventoryMismatch, ...],
        mismatched_collection_names: tuple[str, ...],
        verifier_name: str,
        verifier_version: str,
    ) -> ExtractionProjectionInventoryEquivalenceResult:
        """Create one completed technical comparison result."""
        equivalent = not mismatches and not mismatched_collection_names
        disposition = (
            ExtractionActionDisposition.CONTINUE
            if equivalent
            else ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
        )
        replay_inventory_id = (
            request.replay_materialization.inventory_id
            if request.replay_materialization is not None
            else None
        )
        values = (
            request.request_id,
            request.idempotency_key,
            ExtractionActionStatus.COMPLETED,
            disposition,
            request.kind,
            request.expected.expected_inventory_id,
            request.observed.inventory_id,
            replay_inventory_id,
            equivalent,
            mismatches,
            mismatched_collection_names,
            verifier_name,
            verifier_version,
        )
        return cls(
            result_id=stable_id(
                "extraction-projection-inventory-equivalence-result",
                cls.CONTRACT_VERSION,
                values,
            ),
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            status=ExtractionActionStatus.COMPLETED,
            disposition=disposition,
            kind=request.kind,
            expected_inventory_id=request.expected.expected_inventory_id,
            observed_inventory_id=request.observed.inventory_id,
            replay_materialization_inventory_id=replay_inventory_id,
            equivalent=equivalent,
            mismatches=mismatches,
            mismatched_collection_names=mismatched_collection_names,
            verifier_name=verifier_name,
            verifier_version=verifier_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported inventory-equivalence result")
        if self.status is not ExtractionActionStatus.COMPLETED:
            raise ValueError(
                "inventory-equivalence comparison did not complete"
            )
        if not isinstance(self.kind, ExtractionProjectionEquivalenceKind):
            raise TypeError("inventory-equivalence kind is invalid")
        for inventory_id in (
            self.expected_inventory_id,
            self.observed_inventory_id,
        ):
            if type(inventory_id) is not str or not inventory_id:
                raise ValueError("inventory-equivalence identity is invalid")
        if (
            self.kind is ExtractionProjectionEquivalenceKind.SAME_STORE_REPLAY
        ) != (self.replay_materialization_inventory_id is not None):
            raise ValueError("replay materialization identity is inconsistent")
        if type(self.equivalent) is not bool:
            raise TypeError("inventory-equivalence outcome is invalid")
        if (
            not isinstance(self.mismatches, tuple)
            or self.mismatches != tuple(sorted(set(self.mismatches)))
            or any(
                not isinstance(item, ExtractionProjectionInventoryMismatch)
                for item in self.mismatches
            )
        ):
            raise ValueError(
                "inventory-equivalence mismatches are not canonical"
            )
        if (
            not isinstance(self.mismatched_collection_names, tuple)
            or self.mismatched_collection_names
            != tuple(sorted(set(self.mismatched_collection_names)))
            or any(
                type(name) is not str or not name
                for name in self.mismatched_collection_names
            )
        ):
            raise ValueError("mismatched collection names are not canonical")
        if not self.verifier_name or not self.verifier_version:
            raise ValueError("inventory-equivalence verifier is incomplete")
        expected_equivalent = not self.mismatches and not (
            self.mismatched_collection_names
        )
        expected_disposition = (
            ExtractionActionDisposition.CONTINUE
            if expected_equivalent
            else ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
        )
        if (
            self.equivalent != expected_equivalent
            or self.disposition is not expected_disposition
        ):
            raise ValueError("inventory-equivalence outcome is inconsistent")
        values = (
            self.request_id,
            self.idempotency_key,
            self.status,
            self.disposition,
            self.kind,
            self.expected_inventory_id,
            self.observed_inventory_id,
            self.replay_materialization_inventory_id,
            self.equivalent,
            self.mismatches,
            self.mismatched_collection_names,
            self.verifier_name,
            self.verifier_version,
        )
        expected = stable_id(
            "extraction-projection-inventory-equivalence-result",
            self.CONTRACT_VERSION,
            values,
        )
        if self.result_id != expected:
            raise ValueError("inventory-equivalence result ID is inconsistent")

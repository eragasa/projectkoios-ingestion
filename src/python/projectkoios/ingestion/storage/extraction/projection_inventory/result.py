"""Typed query-only extraction projection inventory result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.actions.status import (
    ExtractionActionStatus,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.collection import (  # noqa: E501
    ExtractionProjectionCollectionInventory,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.request import (  # noqa: E501
    ExtractionProjectionInventoryRequest,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionInventoryResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Compact owned-collection evidence or one typed query failure."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    request_id: str
    idempotency_key: str
    projection_reference: str
    status: ExtractionActionStatus
    disposition: ExtractionActionDisposition
    failure_code: str | None
    inventory_id: str | None
    collections: tuple[ExtractionProjectionCollectionInventory, ...]
    actionizer_name: str
    actionizer_version: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def completed(
        cls,
        *,
        request: ExtractionProjectionInventoryRequest,
        collections: tuple[ExtractionProjectionCollectionInventory, ...],
        actionizer_name: str,
        actionizer_version: str,
    ) -> ExtractionProjectionInventoryResult:
        inventory_id = stable_id(
            "extraction-projection-inventory",
            cls.CONTRACT_VERSION,
            request.projection_reference,
            tuple(item.inventory_id for item in collections),
        )
        return cls._create(
            request=request,
            status=ExtractionActionStatus.COMPLETED,
            disposition=ExtractionActionDisposition.CONTINUE,
            failure_code=None,
            inventory_id=inventory_id,
            collections=collections,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    @classmethod
    def failed(
        cls,
        *,
        request: ExtractionProjectionInventoryRequest,
        disposition: ExtractionActionDisposition,
        failure_code: str,
        actionizer_name: str,
        actionizer_version: str,
    ) -> ExtractionProjectionInventoryResult:
        if disposition is ExtractionActionDisposition.CONTINUE:
            raise ValueError("failed projection inventory cannot continue")
        return cls._create(
            request=request,
            status=ExtractionActionStatus.FAILED,
            disposition=disposition,
            failure_code=failure_code,
            inventory_id=None,
            collections=(),
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    @classmethod
    def _create(
        cls,
        *,
        request: ExtractionProjectionInventoryRequest,
        status: ExtractionActionStatus,
        disposition: ExtractionActionDisposition,
        failure_code: str | None,
        inventory_id: str | None,
        collections: tuple[ExtractionProjectionCollectionInventory, ...],
        actionizer_name: str,
        actionizer_version: str,
    ) -> ExtractionProjectionInventoryResult:
        return cls(
            result_id=stable_id(
                "extraction-projection-inventory-result",
                cls.CONTRACT_VERSION,
                request.request_id,
                request.idempotency_key,
                request.projection_reference,
                status,
                disposition,
                failure_code,
                inventory_id,
                tuple(item.inventory_id for item in collections),
                actionizer_name,
                actionizer_version,
            ),
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            projection_reference=request.projection_reference,
            status=status,
            disposition=disposition,
            failure_code=failure_code,
            inventory_id=inventory_id,
            collections=collections,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported projection-inventory result contract")
        if not isinstance(
            self.status, ExtractionActionStatus
        ) or not isinstance(self.disposition, ExtractionActionDisposition):
            raise TypeError("projection-inventory outcome is invalid")
        if (
            not self.request_id
            or not self.idempotency_key
            or not self.projection_reference
        ):
            raise ValueError(
                "projection-inventory result identity is incomplete"
            )
        if (
            type(self.projection_reference) is not str
            or not self.projection_reference
            or len(self.projection_reference) > 4_096
        ):
            raise ValueError("projection reference is invalid")
        if not self.actionizer_name or not self.actionizer_version:
            raise ValueError("projection-inventory actionizer is incomplete")
        if self.failure_code is not None and (
            type(self.failure_code) is not str
            or not self.failure_code
            or len(self.failure_code) > 256
        ):
            raise ValueError("projection-inventory failure code is invalid")
        if not isinstance(self.collections, tuple) or any(
            not isinstance(item, ExtractionProjectionCollectionInventory)
            for item in self.collections
        ):
            raise TypeError("projection collections are invalid")
        names = tuple(item.collection_name for item in self.collections)
        if names != tuple(sorted(set(names))):
            raise ValueError("projection collections are not canonical")
        if self.status is ExtractionActionStatus.COMPLETED:
            expected_inventory = stable_id(
                "extraction-projection-inventory",
                self.CONTRACT_VERSION,
                self.projection_reference,
                tuple(item.inventory_id for item in self.collections),
            )
            if (
                self.disposition is not ExtractionActionDisposition.CONTINUE
                or self.failure_code is not None
                or self.inventory_id != expected_inventory
            ):
                raise ValueError("completed projection inventory is invalid")
        elif (
            self.status is not ExtractionActionStatus.FAILED
            or self.disposition is ExtractionActionDisposition.CONTINUE
            or not self.failure_code
            or self.inventory_id is not None
            or self.collections
        ):
            raise ValueError("failed projection inventory is invalid")
        expected = stable_id(
            "extraction-projection-inventory-result",
            self.CONTRACT_VERSION,
            self.request_id,
            self.idempotency_key,
            self.projection_reference,
            self.status,
            self.disposition,
            self.failure_code,
            self.inventory_id,
            tuple(item.inventory_id for item in self.collections),
            self.actionizer_name,
            self.actionizer_version,
        )
        if self.result_id != expected:
            raise ValueError("projection-inventory result ID is inconsistent")

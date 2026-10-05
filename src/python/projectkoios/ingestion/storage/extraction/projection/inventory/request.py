"""Typed provider request for an extraction projector inventory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.base.inventory.request import InventoryRequest
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.configuration import (  # noqa: E501
    ExtractionProjectionInventoryConfiguration,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionInventoryRequest(
    AbstractImmutableDataObject,
    ConfigurableDataObjectActionRequest[
        ExtractionProjectionInventoryConfiguration
    ],
):
    """Bind an explicit projection target, configuration, and authority."""

    CONTRACT_NAME: ClassVar[str] = "extraction-projection-inventory-request"
    CONTRACT_VERSION: ClassVar[str] = "2.0"
    AUTHORITY_REQUIREMENT: ClassVar[str] = "extraction_projection_query"

    request_id: str
    idempotency_key: str
    target: ExtractionProjectionTargetIdentity
    configuration: ExtractionProjectionInventoryConfiguration
    authority_id: str
    contract_version: str = CONTRACT_VERSION

    @property
    def projection_reference(self) -> str:
        """Return the stable target identity used by legacy result fields."""
        return self.target.target_id

    @classmethod
    def create(
        cls,
        *,
        target: ExtractionProjectionTargetIdentity,
        configuration: ExtractionProjectionInventoryConfiguration,
        authority_id: str,
    ) -> ExtractionProjectionInventoryRequest:
        """Create a typed request from the generic inventory request."""
        generic = InventoryRequest.create(
            target=target,
            configuration=configuration,
            authority_id=authority_id,
        )
        return cls(
            request_id=stable_id(
                "extraction-projection-inventory-request",
                cls.CONTRACT_VERSION,
                generic.request_id,
            ),
            idempotency_key=generic.idempotency_key,
            target=target,
            configuration=configuration,
            authority_id=authority_id,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported projection-inventory request")
        if type(self.target) is not ExtractionProjectionTargetIdentity:
            raise TypeError("projection inventory target is invalid")
        if (
            type(self.configuration)
            is not ExtractionProjectionInventoryConfiguration
        ):
            raise TypeError("projection inventory configuration is invalid")
        generic = InventoryRequest.create(
            target=self.target,
            configuration=self.configuration,
            authority_id=self.authority_id,
        )
        if self.idempotency_key != generic.idempotency_key:
            raise ValueError("projection-inventory idempotency is inconsistent")
        expected = stable_id(
            "extraction-projection-inventory-request",
            self.CONTRACT_VERSION,
            generic.request_id,
        )
        if self.request_id != expected:
            raise ValueError("projection-inventory request ID is inconsistent")

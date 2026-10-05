"""Read-only inventory pattern for materialized projector output."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.inventory.identity_error import (
    InventoryIdentityError,
)
from projectkoios.ingestion.base.inventory.inventory import Inventory
from projectkoios.ingestion.base.inventory.request import InventoryRequest
from projectkoios.ingestion.base.projector.inventory.configuration import (
    AbstractProjectorInventoryConfiguration,
)
from projectkoios.ingestion.base.projector.inventory.evidence import (
    AbstractProjectorInventoryEvidence,
)
from projectkoios.ingestion.base.projector.inventory.target import (
    AbstractProjectorInventoryTarget,
)


class ProjectorInventory[
    TargetT: AbstractProjectorInventoryTarget,
    ConfigurationT: AbstractProjectorInventoryConfiguration,
    EvidenceT: AbstractProjectorInventoryEvidence,
](
    Inventory[TargetT, ConfigurationT, EvidenceT],
    ABC,
):
    """Inventory stored output bound to one projector schema and target."""

    __slots__ = ()

    def _validate_request_identity(
        self,
        *,
        request: InventoryRequest[TargetT, ConfigurationT],
    ) -> None:
        if request.target.schema_id != request.configuration.schema_id:
            raise InventoryIdentityError(
                "projector inventory schema identities differ"
            )

    def _validate_evidence_identity(
        self,
        *,
        request: InventoryRequest[TargetT, ConfigurationT],
        evidence: EvidenceT,
    ) -> None:
        if evidence.schema_id != request.target.schema_id:
            raise InventoryIdentityError(
                "projector inventory evidence schema differs"
            )

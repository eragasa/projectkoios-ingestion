"""Explicit identity of one extraction projection target."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.materializer.target import (
    AbstractMaterializationTarget,
)
from projectkoios.ingestion.base.projector.inventory.target import (
    AbstractProjectorInventoryTarget,
)
from projectkoios.ingestion.identity import stable_id

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,255}")


@dataclass(frozen=True, slots=True)
class ExtractionProjectionTargetIdentity(
    AbstractMaterializationTarget,
    AbstractProjectorInventoryTarget,
):
    """Identify one deployment, database, schema, and projection slot.

    Parameters
    ----------
    target_id
        Stable globally unambiguous identity over all target dimensions.
    deployment_id
        Explicit deployment identity; never inferred from a database name.
    environment
        Explicit environment such as ``development`` or ``production``.
    database_name
        Exact database resource name within the deployment.
    schema_id
        Logical read-model schema accepted by the target slot.
    projection_slot
        Stable slot distinguishing independently rebuildable projections.
    contract_version
        Version of this target identity contract.
    """

    CONTRACT_NAME: ClassVar[str] = "extraction-projection-target-identity"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    target_id: str
    deployment_id: str
    environment: str
    database_name: str
    schema_id: str
    projection_slot: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        deployment_id: str,
        environment: str,
        database_name: str,
        schema_id: str,
        projection_slot: str,
    ) -> ExtractionProjectionTargetIdentity:
        """Create one target identity from every resource dimension."""
        parts = (
            deployment_id,
            environment,
            database_name,
            schema_id,
            projection_slot,
        )
        return cls(
            target_id=stable_id(
                "extraction-projection-target",
                cls.CONTRACT_VERSION,
                parts,
            ),
            deployment_id=deployment_id,
            environment=environment,
            database_name=database_name,
            schema_id=schema_id,
            projection_slot=projection_slot,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported extraction projection target")
        parts = (
            self.deployment_id,
            self.environment,
            self.database_name,
            self.schema_id,
            self.projection_slot,
        )
        if any(
            type(value) is not str or not _NAME.fullmatch(value)
            for value in parts
        ):
            raise ValueError("extraction projection target is incomplete")
        expected = stable_id(
            "extraction-projection-target",
            self.CONTRACT_VERSION,
            parts,
        )
        if self.target_id != expected:
            raise ValueError("extraction projection target ID is inconsistent")

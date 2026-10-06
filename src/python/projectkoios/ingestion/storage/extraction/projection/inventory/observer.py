"""Typed read-only inventory of one extraction projection target."""

from __future__ import annotations

from projectkoios.ingestion.base.inventory.identity.error import (
    InventoryIdentityError,
)
from projectkoios.ingestion.base.inventory.identity.model import (
    InventoryIdentity,
)
from projectkoios.ingestion.base.projector.inventory.observer import (
    ProjectorInventory,
)
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.configuration import (  # noqa: E501
    ExtractionProjectionInventoryConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.evidence import (  # noqa: E501
    ExtractionProjectionInventoryEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.reader.base import (  # noqa: E501
    ExtractionProjectionInventoryReader,
)


class ExtractionProjectorInventory(
    ProjectorInventory[
        ExtractionProjectionTargetIdentity,
        ExtractionProjectionInventoryConfiguration,
        ExtractionProjectionInventoryEvidence,
    ]
):
    """Observe complete stored content for an extraction projection."""

    __slots__ = ("reader",)

    AUTHORITY_REQUIREMENT = "extraction_projection_query"
    authority_requirement = AUTHORITY_REQUIREMENT
    target_type = ExtractionProjectionTargetIdentity
    configuration_type = ExtractionProjectionInventoryConfiguration
    evidence_type = ExtractionProjectionInventoryEvidence
    identity = InventoryIdentity.create(
        name="extraction-projector-inventory",
        version="1.0",
        target_contract=ExtractionProjectionTargetIdentity.CONTRACT_NAME,
        configuration_contract=(
            ExtractionProjectionInventoryConfiguration.CONTRACT_NAME
        ),
        evidence_contract=ExtractionProjectionInventoryEvidence.CONTRACT_NAME,
        authority_requirement=AUTHORITY_REQUIREMENT,
    )

    def __init__(self, *, reader: ExtractionProjectionInventoryReader) -> None:
        if not isinstance(reader, ExtractionProjectionInventoryReader):
            raise TypeError("reader has the wrong inventory contract")
        self.reader = reader

    def observe(
        self,
        *,
        target: ExtractionProjectionTargetIdentity,
        configuration: ExtractionProjectionInventoryConfiguration,
        authority_id: str,
    ) -> ExtractionProjectionInventoryEvidence:
        """Read and aggregate exact collection content evidence."""
        collections = self.reader.read_inventory(
            target=target,
            configuration=configuration,
            authority_id=authority_id,
        )
        if tuple(item.collection_name for item in collections) != (
            configuration.collection_names
        ):
            raise InventoryIdentityError("projection collection set differs")
        return ExtractionProjectionInventoryEvidence.create(
            target_id=target.target_id,
            configuration_id=configuration.configuration_id,
            authority_id=authority_id,
            schema_id=target.schema_id,
            collections=collections,
        )

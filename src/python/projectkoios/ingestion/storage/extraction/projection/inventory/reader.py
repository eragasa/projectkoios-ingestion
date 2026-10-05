"""Nominal query port for extraction projection inventories."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.collection import (  # noqa: E501
    ExtractionProjectionCollectionInventory,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.configuration import (  # noqa: E501
    ExtractionProjectionInventoryConfiguration,
)


class ExtractionProjectionInventoryReader(ABC):
    """Read full-content collection inventories from one explicit target."""

    @abstractmethod
    def read_inventory(
        self,
        *,
        target: ExtractionProjectionTargetIdentity,
        configuration: ExtractionProjectionInventoryConfiguration,
        authority_id: str,
    ) -> tuple[ExtractionProjectionCollectionInventory, ...]:
        """Return every configured collection once in canonical order."""

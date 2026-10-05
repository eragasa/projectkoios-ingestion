"""Nominal query port for extraction projection inventories."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.storage.extraction.projection_inventory.collection import (  # noqa: E501
    ExtractionProjectionCollectionInventory,
)


class ExtractionProjectionInventoryReader(ABC):
    """Read compact owned-collection inventories from one projection."""

    @abstractmethod
    def read_inventory(
        self,
        *,
        projection_reference: str,
        authority_id: str,
    ) -> tuple[ExtractionProjectionCollectionInventory, ...]:
        """Return every owned collection exactly once in canonical order."""

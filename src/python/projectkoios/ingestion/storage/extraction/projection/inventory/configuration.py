"""Complete extraction projector-inventory configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.projector.inventory.configuration import (
    AbstractProjectorInventoryConfiguration,
)
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class ExtractionProjectionInventoryConfiguration(
    AbstractProjectorInventoryConfiguration
):
    """Bind physical collections and inventory bounds for one schema."""

    CONTRACT_NAME: ClassVar[str] = (
        "extraction-projection-inventory-configuration"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    configuration_id: str
    schema_id: str
    collection_names: tuple[str, ...]
    maximum_documents_per_collection: int
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def mongodb_v1(cls) -> ExtractionProjectionInventoryConfiguration:
        """Return the complete MongoDB extraction inventory configuration."""
        names = tuple(
            sorted(
                (
                    "extraction_blocks",
                    "extraction_documents",
                    "extraction_manifests",
                    "extraction_pages",
                    "extraction_warnings",
                )
            )
        )
        maximum = 50_000_000
        return cls(
            configuration_id=stable_id(
                "extraction-projection-inventory-configuration",
                cls.CONTRACT_VERSION,
                "extraction-read-model-v1",
                names,
                maximum,
            ),
            schema_id="extraction-read-model-v1",
            collection_names=names,
            maximum_documents_per_collection=maximum,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported extraction inventory configuration")
        if type(self.schema_id) is not str or not self.schema_id:
            raise ValueError("inventory schema is invalid")
        if (
            not isinstance(self.collection_names, tuple)
            or self.collection_names
            != tuple(sorted(set(self.collection_names)))
            or any(
                type(name) is not str or not name
                for name in self.collection_names
            )
        ):
            raise ValueError("inventory collection names are not canonical")
        if (
            isinstance(self.maximum_documents_per_collection, bool)
            or not isinstance(self.maximum_documents_per_collection, int)
            or self.maximum_documents_per_collection <= 0
        ):
            raise ValueError("inventory document bound is invalid")
        expected = stable_id(
            "extraction-projection-inventory-configuration",
            self.CONTRACT_VERSION,
            self.schema_id,
            self.collection_names,
            self.maximum_documents_per_collection,
        )
        if self.configuration_id != expected:
            raise ValueError("inventory configuration ID is inconsistent")

"""Complete extraction projector-inventory configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.projector.inventory.configuration import (
    AbstractProjectorInventoryConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.projection.collection import (
    ExtractionProjectionCollection,
)


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
    documents_collection: str
    pages_collection: str
    blocks_collection: str
    warnings_collection: str
    manifests_collection: str
    maximum_documents_per_collection: int
    contract_version: str = CONTRACT_VERSION

    @property
    def collection_names(self) -> tuple[str, ...]:
        """Return physical collection names in canonical lexical order."""
        return tuple(
            sorted(
                (
                    self.documents_collection,
                    self.pages_collection,
                    self.blocks_collection,
                    self.warnings_collection,
                    self.manifests_collection,
                )
            )
        )

    @classmethod
    def mongodb_v1(cls) -> ExtractionProjectionInventoryConfiguration:
        """Return the complete MongoDB extraction inventory configuration."""
        schema = "extraction-read-model-v1"
        documents = "extraction_documents"
        pages = "extraction_pages"
        blocks = "extraction_blocks"
        warnings = "extraction_warnings"
        manifests = "extraction_manifests"
        maximum = 50_000_000
        values = (
            schema,
            documents,
            pages,
            blocks,
            warnings,
            manifests,
            maximum,
        )
        return cls(
            configuration_id=stable_id(
                "extraction-projection-inventory-configuration",
                cls.CONTRACT_VERSION,
                values,
            ),
            schema_id=schema,
            documents_collection=documents,
            pages_collection=pages,
            blocks_collection=blocks,
            warnings_collection=warnings,
            manifests_collection=manifests,
            maximum_documents_per_collection=maximum,
        )

    def collection_name(
        self,
        collection: ExtractionProjectionCollection,
    ) -> str:
        """Map one logical projection collection to its physical name."""
        return {
            ExtractionProjectionCollection.DOCUMENTS: self.documents_collection,
            ExtractionProjectionCollection.PAGES: self.pages_collection,
            ExtractionProjectionCollection.BLOCKS: self.blocks_collection,
            ExtractionProjectionCollection.WARNINGS: self.warnings_collection,
            ExtractionProjectionCollection.MANIFESTS: self.manifests_collection,
        }[collection]

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported extraction inventory configuration")
        names = (
            self.documents_collection,
            self.pages_collection,
            self.blocks_collection,
            self.warnings_collection,
            self.manifests_collection,
        )
        if (
            type(self.schema_id) is not str
            or not self.schema_id
            or any(type(name) is not str or not name for name in names)
            or len(set(names)) != len(names)
        ):
            raise ValueError("inventory configuration is incomplete")
        if (
            isinstance(self.maximum_documents_per_collection, bool)
            or not isinstance(self.maximum_documents_per_collection, int)
            or self.maximum_documents_per_collection <= 0
        ):
            raise ValueError("inventory document bound is invalid")
        values = (
            self.schema_id,
            *names,
            self.maximum_documents_per_collection,
        )
        expected = stable_id(
            "extraction-projection-inventory-configuration",
            self.CONTRACT_VERSION,
            values,
        )
        if self.configuration_id != expected:
            raise ValueError("inventory configuration ID is inconsistent")

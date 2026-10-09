"""Physical write configuration for extraction projection materialization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.materializer.configuration import (
    AbstractMaterializationConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.projection.collection import (
    ExtractionProjectionCollection,
)

_COLLECTION = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,119}")


@dataclass(frozen=True, slots=True)
class ExtractionProjectionMaterializationConfiguration(
    AbstractMaterializationConfiguration
):
    """Bind logical collection roles to exact physical collection names.

    Parameters
    ----------
    configuration_id
        Stable identity over schema, names, and byte bound.
    schema_id
        Logical extraction read-model schema.
    documents_collection
        Physical root-document collection.
    pages_collection
        Physical page collection.
    blocks_collection
        Physical block collection.
    warnings_collection
        Physical warning collection.
    manifests_collection
        Physical extraction-manifest collection.
    maximum_document_bytes
        Maximum BSON bytes accepted for one projected document.
    contract_version
        Version of this physical configuration contract.
    """

    CONTRACT_NAME: ClassVar[str] = (
        "extraction-projection-materialization-configuration"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    configuration_id: str
    schema_id: str
    documents_collection: str
    pages_collection: str
    blocks_collection: str
    warnings_collection: str
    manifests_collection: str
    maximum_document_bytes: int
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def mongodb_v1(
        cls,
    ) -> ExtractionProjectionMaterializationConfiguration:
        """Return the complete version-one MongoDB physical mapping."""
        schema_id = "extraction-read-model-v1"
        documents = "extraction_documents"
        pages = "extraction_pages"
        blocks = "extraction_blocks"
        warnings = "extraction_warnings"
        manifests = "extraction_manifests"
        maximum_bytes = 15_000_000
        values = (
            schema_id,
            documents,
            pages,
            blocks,
            warnings,
            manifests,
            maximum_bytes,
        )
        return cls(
            configuration_id=stable_id(
                "extraction-projection-materialization-configuration",
                cls.CONTRACT_VERSION,
                values,
            ),
            schema_id=schema_id,
            documents_collection=documents,
            pages_collection=pages,
            blocks_collection=blocks,
            warnings_collection=warnings,
            manifests_collection=manifests,
            maximum_document_bytes=maximum_bytes,
        )

    def collection_name(
        self, collection: ExtractionProjectionCollection
    ) -> str:
        """Return the exact physical name for one logical collection."""
        if not isinstance(collection, ExtractionProjectionCollection):
            raise TypeError("extraction collection is invalid")
        names = {
            ExtractionProjectionCollection.DOCUMENTS: (
                self.documents_collection
            ),
            ExtractionProjectionCollection.PAGES: self.pages_collection,
            ExtractionProjectionCollection.BLOCKS: self.blocks_collection,
            ExtractionProjectionCollection.WARNINGS: self.warnings_collection,
            ExtractionProjectionCollection.MANIFESTS: (
                self.manifests_collection
            ),
        }
        try:
            return names[collection]
        except KeyError as error:
            raise ValueError("unsupported extraction collection") from error

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported materialization configuration")
        collections = (
            self.documents_collection,
            self.pages_collection,
            self.blocks_collection,
            self.warnings_collection,
            self.manifests_collection,
        )
        if (
            type(self.schema_id) is not str
            or not self.schema_id
            or any(
                type(collection) is not str
                or not _COLLECTION.fullmatch(collection)
                for collection in collections
            )
        ):
            raise ValueError("materialization configuration is incomplete")
        if len(collections) != len(set(collections)):
            raise ValueError("materialization collections must be unique")
        if (
            isinstance(self.maximum_document_bytes, bool)
            or not isinstance(self.maximum_document_bytes, int)
            or not 1 <= self.maximum_document_bytes <= 16_000_000
        ):
            raise ValueError("materialization document bound is invalid")
        values = (
            self.schema_id,
            *collections,
            self.maximum_document_bytes,
        )
        expected = stable_id(
            "extraction-projection-materialization-configuration",
            self.CONTRACT_VERSION,
            values,
        )
        if self.configuration_id != expected:
            raise ValueError("materialization configuration ID is inconsistent")

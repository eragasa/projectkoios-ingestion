"""Complete extraction projection index-readiness configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.projection.index.readiness.definition import (  # noqa: E501
    ExtractionProjectionIndexDefinition,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionIndexReadinessConfiguration(
    AbstractActionConfiguration
):
    """Bind a projection schema to every required secondary index."""

    CONTRACT_NAME: ClassVar[str] = (
        "extraction-projection-index-readiness-configuration"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_INDEXES: ClassVar[int] = 64

    configuration_id: str
    schema_id: str
    indexes: tuple[ExtractionProjectionIndexDefinition, ...]
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def mongodb_v1(
        cls,
    ) -> ExtractionProjectionIndexReadinessConfiguration:
        """Return all required indexes for extraction read-model version one."""
        indexes = tuple(
            sorted(
                (
                    ExtractionProjectionIndexDefinition.create(
                        collection_name="extraction_documents",
                        index_name=(
                            "publication_state_1_source.content_hash_1"
                        ),
                        keys=(
                            ("publication_state", 1),
                            ("source.content_hash", 1),
                        ),
                        unique=False,
                    ),
                    ExtractionProjectionIndexDefinition.create(
                        collection_name="extraction_pages",
                        index_name="manifest_id_1_page_index_1",
                        keys=(("manifest_id", 1), ("page_index", 1)),
                        unique=True,
                    ),
                    ExtractionProjectionIndexDefinition.create(
                        collection_name="extraction_blocks",
                        index_name="manifest_id_1_page_index_1_ordinal_1",
                        keys=(
                            ("manifest_id", 1),
                            ("page_index", 1),
                            ("ordinal", 1),
                        ),
                        unique=True,
                    ),
                    ExtractionProjectionIndexDefinition.create(
                        collection_name="extraction_warnings",
                        index_name="document_id_1_code_1",
                        keys=(("document_id", 1), ("code", 1)),
                        unique=False,
                    ),
                    ExtractionProjectionIndexDefinition.create(
                        collection_name="extraction_manifests",
                        index_name="source_blob_id_1_status_1",
                        keys=(("source_blob_id", 1), ("status", 1)),
                        unique=False,
                    ),
                ),
                key=lambda item: (item.collection_name, item.index_name),
            )
        )
        return cls(
            configuration_id=stable_id(
                "extraction-projection-index-readiness-configuration",
                cls.CONTRACT_VERSION,
                "extraction-read-model-v1",
                tuple(item.index_definition_id for item in indexes),
            ),
            schema_id="extraction-read-model-v1",
            indexes=indexes,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported index-readiness configuration")
        if (
            type(self.schema_id) is not str
            or not self.schema_id
            or len(self.schema_id) > 4_096
        ):
            raise ValueError("index-readiness schema is invalid")
        if (
            not isinstance(self.indexes, tuple)
            or len(self.indexes) > self.MAXIMUM_INDEXES
            or any(
                type(item) is not ExtractionProjectionIndexDefinition
                for item in self.indexes
            )
        ):
            raise TypeError("index-readiness definitions are invalid")
        keys = tuple(
            (item.collection_name, item.index_name) for item in self.indexes
        )
        if not keys or keys != tuple(sorted(set(keys))):
            raise ValueError("index-readiness definitions are not canonical")
        expected = stable_id(
            "extraction-projection-index-readiness-configuration",
            self.CONTRACT_VERSION,
            self.schema_id,
            tuple(item.index_definition_id for item in self.indexes),
        )
        if self.configuration_id != expected:
            raise ValueError("index-readiness configuration ID is inconsistent")

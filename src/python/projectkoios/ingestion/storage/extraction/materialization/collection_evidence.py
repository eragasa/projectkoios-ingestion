"""Outcome evidence for one logical extraction projection collection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.projection.collection import (
    ExtractionProjectionCollection,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionMaterializationCollectionEvidence(
    AbstractImmutableDataObject
):
    """Count newly created and unchanged documents in one collection."""

    CONTRACT_NAME: ClassVar[str] = (
        "extraction-projection-materialization-collection-evidence"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    collection_evidence_id: str
    collection: ExtractionProjectionCollection
    created_document_count: int
    unchanged_document_count: int
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        collection: ExtractionProjectionCollection,
        created_document_count: int,
        unchanged_document_count: int,
    ) -> ExtractionProjectionMaterializationCollectionEvidence:
        """Create exact bounded count evidence for one logical collection."""
        return cls(
            collection_evidence_id=stable_id(
                "extraction-projection-materialization-collection-evidence",
                cls.CONTRACT_VERSION,
                collection.value,
                created_document_count,
                unchanged_document_count,
            ),
            collection=collection,
            created_document_count=created_document_count,
            unchanged_document_count=unchanged_document_count,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported collection evidence contract")
        if not isinstance(self.collection, ExtractionProjectionCollection):
            raise TypeError("materialization collection is invalid")
        for value in (
            self.created_document_count,
            self.unchanged_document_count,
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError("materialization count is invalid")
        expected = stable_id(
            "extraction-projection-materialization-collection-evidence",
            self.CONTRACT_VERSION,
            self.collection.value,
            self.created_document_count,
            self.unchanged_document_count,
        )
        if self.collection_evidence_id != expected:
            raise ValueError("collection evidence ID is inconsistent")

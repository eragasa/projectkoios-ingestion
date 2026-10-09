"""Bounded aggregate extraction materialization evidence inventory."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.materialization.evidence.model import (  # noqa: E501
    ExtractionProjectionMaterializationEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.collection import (
    ExtractionProjectionCollection,
)


@dataclass(frozen=True, slots=True, init=False)
class ExtractionProjectionMaterializationEvidenceInventory:
    """Own canonical per-projection outcomes for one exact target."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_ITEMS: ClassVar[int] = 10_000_000

    _items: tuple[ExtractionProjectionMaterializationEvidence, ...] = field(
        repr=True
    )
    inventory_id: str = field(init=False)
    projection_count: int = field(init=False)
    projection_ids_sha256: str = field(init=False)
    target_id: str = field(init=False)
    configuration_id: str = field(init=False)
    projected_document_count: int = field(init=False)
    created_document_count: int = field(init=False)
    unchanged_document_count: int = field(init=False)

    def __init__(
        self,
        *items: ExtractionProjectionMaterializationEvidence,
    ) -> None:
        values = tuple(items)
        if not 1 <= len(values) <= self.MAXIMUM_ITEMS:
            raise ValueError("materialization evidence count is out of bounds")
        if any(
            type(value) is not ExtractionProjectionMaterializationEvidence
            for value in values
        ):
            raise TypeError("materialization inventory items are invalid")
        projection_ids = tuple(value.projection_id for value in values)
        if projection_ids != tuple(sorted(projection_ids)):
            raise ValueError("materialization evidence must be canonical")
        if len(projection_ids) != len(set(projection_ids)):
            raise ValueError("materialization projections must be unique")
        target_ids = {value.target_id for value in values}
        configuration_ids = {value.configuration_id for value in values}
        if len(target_ids) != 1 or len(configuration_ids) != 1:
            raise ValueError("materialization evidence scope differs")
        evidence_digest = hashlib.sha256()
        projection_digest = hashlib.sha256()
        for value in values:
            for digest, component in (
                (evidence_digest, value.evidence_id),
                (projection_digest, value.projection_id),
            ):
                encoded = component.encode("utf-8", errors="strict")
                digest.update(len(encoded).to_bytes(8, byteorder="big"))
                digest.update(encoded)
        target_id = values[0].target_id
        configuration_id = values[0].configuration_id
        projected = sum(value.projected_document_count for value in values)
        created = sum(value.created_document_count for value in values)
        unchanged = sum(value.unchanged_document_count for value in values)
        projection_ids_sha256 = projection_digest.hexdigest()
        object.__setattr__(self, "_items", values)
        object.__setattr__(self, "projection_count", len(values))
        object.__setattr__(self, "projection_ids_sha256", projection_ids_sha256)
        object.__setattr__(self, "target_id", target_id)
        object.__setattr__(self, "configuration_id", configuration_id)
        object.__setattr__(self, "projected_document_count", projected)
        object.__setattr__(self, "created_document_count", created)
        object.__setattr__(self, "unchanged_document_count", unchanged)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "extraction-projection-materialization-evidence-inventory",
                self.CONTRACT_VERSION,
                len(values),
                target_id,
                configuration_id,
                projected,
                created,
                unchanged,
                projection_ids_sha256,
                evidence_digest.hexdigest(),
            ),
        )

    def __iter__(
        self,
    ) -> Iterator[ExtractionProjectionMaterializationEvidence]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def collection_counts(
        self,
    ) -> dict[ExtractionProjectionCollection, tuple[int, int]]:
        """Return exact created and unchanged counts by logical collection."""
        counts = {
            collection: [0, 0] for collection in ExtractionProjectionCollection
        }
        for evidence in self._items:
            for collection in evidence.collections:
                values = counts[collection.collection]
                values[0] += collection.created_document_count
                values[1] += collection.unchanged_document_count
        return {
            collection: (values[0], values[1])
            for collection, values in counts.items()
        }

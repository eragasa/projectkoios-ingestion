"""Compact backend-neutral reading-evidence materialization outcomes."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.materializer.evidence import (
    AbstractMaterializationEvidence,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.collection import (  # noqa: E501
    ReadingEvidenceStorageCollection,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceMaterializationCollectionEvidence:
    """Retain created and unchanged counts for one logical collection."""

    collection: ReadingEvidenceStorageCollection
    created_count: int
    unchanged_count: int
    evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.collection, ReadingEvidenceStorageCollection):
            raise TypeError("collection has an unsupported type")
        for value, name in (
            (self.created_count, "created_count"),
            (self.unchanged_count, "unchanged_count"),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be non-negative")
        object.__setattr__(
            self,
            "evidence_id",
            stable_id(
                "reading-evidence-materialization-collection",
                self.collection.value,
                self.created_count,
                self.unchanged_count,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class ReadingEvidenceMaterializationCollectionEvidenceInventory:
    """Own exact outcome evidence for every logical collection."""

    _items: tuple[ReadingEvidenceMaterializationCollectionEvidence, ...] = (
        field(repr=True)
    )

    def __init__(
        self, *items: ReadingEvidenceMaterializationCollectionEvidence
    ) -> None:
        values = tuple(items)
        if any(
            type(value) is not ReadingEvidenceMaterializationCollectionEvidence
            for value in values
        ):
            raise TypeError(
                "materialization inventory contains invalid evidence"
            )
        if tuple(value.collection for value in values) != tuple(
            ReadingEvidenceStorageCollection
        ):
            raise ValueError("materialization collection coverage is invalid")
        object.__setattr__(self, "_items", values)

    def __iter__(
        self,
    ) -> Iterator[ReadingEvidenceMaterializationCollectionEvidence]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceMaterializationEvidence(AbstractMaterializationEvidence):
    """Bind exact materialization outcomes to projection and authority."""

    CONTRACT_NAME: ClassVar[str] = "reading-evidence-materialization-evidence"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    projection_id: str
    target_id: str
    configuration_id: str
    authority_id: str
    projected_document_count: int
    collections: ReadingEvidenceMaterializationCollectionEvidenceInventory
    canonical_sha256: SHA256Hash = field(init=False)
    evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        for value, name in (
            (self.projection_id, "projection_id"),
            (self.target_id, "target_id"),
            (self.configuration_id, "configuration_id"),
            (self.authority_id, "authority_id"),
        ):
            if type(value) is not str or not value:
                raise ValueError(f"{name} must be non-empty")
        if (
            type(self.projected_document_count) is not int
            or self.projected_document_count < 1
        ):
            raise ValueError("projected_document_count must be positive")
        if (
            type(self.collections)
            is not ReadingEvidenceMaterializationCollectionEvidenceInventory
        ):
            raise TypeError("collections has an unsupported type")
        total = sum(
            value.created_count + value.unchanged_count
            for value in self.collections
        )
        if total != self.projected_document_count:
            raise ValueError("materialization outcome count differs")
        material = tuple(value.evidence_id for value in self.collections)
        digest = SHA256Fingerprinter.fingerprint(
            content=CanonicalJsonSerializer.serialize_bytes(material)
        )
        object.__setattr__(self, "canonical_sha256", digest)
        object.__setattr__(
            self,
            "evidence_id",
            stable_id(
                "reading-evidence-materialization-evidence",
                self.projection_id,
                self.target_id,
                self.configuration_id,
                self.authority_id,
                self.projected_document_count,
                digest,
            ),
        )

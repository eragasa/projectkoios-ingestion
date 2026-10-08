"""Exact backend-neutral storage collection completion evidence."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.collection import (  # noqa: E501
    ReadingEvidenceStorageCollection,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.inventory import (  # noqa: E501
    ReadingEvidenceStorageDocumentInventory,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceStorageCollectionDigest:
    """Bind one non-completion collection to exact full-content evidence."""

    collection: ReadingEvidenceStorageCollection
    document_count: int
    canonical_sha256: SHA256Hash
    digest_id: str = field(init=False)

    @classmethod
    def observe(
        cls,
        *,
        collection: ReadingEvidenceStorageCollection,
        documents: ReadingEvidenceStorageDocumentInventory,
    ) -> ReadingEvidenceStorageCollectionDigest:
        """Observe one exact collection from complete projected members."""
        if (
            not isinstance(collection, ReadingEvidenceStorageCollection)
            or collection is ReadingEvidenceStorageCollection.COMPLETIONS
        ):
            raise ValueError("completion collection cannot be observed here")
        members = tuple(
            (document.document_id, document.canonical_sha256)
            for document in documents
            if document.kind.collection is collection
        )
        return cls(
            collection=collection,
            document_count=len(members),
            canonical_sha256=SHA256Fingerprinter.fingerprint(
                content=CanonicalJsonSerializer.serialize_bytes(members)
            ),
        )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.collection, ReadingEvidenceStorageCollection)
            or self.collection is ReadingEvidenceStorageCollection.COMPLETIONS
        ):
            raise ValueError("collection digest role is invalid")
        if type(self.document_count) is not int or self.document_count < 0:
            raise ValueError("collection document count is invalid")
        if not SHA256Hash.is_canonical(self.canonical_sha256):
            raise ValueError("collection digest is invalid")
        object.__setattr__(
            self,
            "digest_id",
            stable_id(
                "reading-evidence-storage-collection-digest",
                self.collection.value,
                self.document_count,
                self.canonical_sha256,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class ReadingEvidenceStorageCollectionDigestInventory:
    """Own exact completion evidence for every child collection."""

    _digests: tuple[ReadingEvidenceStorageCollectionDigest, ...] = field(
        repr=True
    )

    def __init__(
        self, *digests: ReadingEvidenceStorageCollectionDigest
    ) -> None:
        values = tuple(digests)
        if any(
            type(value) is not ReadingEvidenceStorageCollectionDigest
            for value in values
        ):
            raise TypeError(
                "collection digest inventory contains invalid value"
            )
        roles = tuple(value.collection for value in values)
        expected = ReadingEvidenceStorageCollection.non_completion()
        if roles != expected:
            raise ValueError("collection digest inventory coverage is invalid")
        object.__setattr__(self, "_digests", values)

    @classmethod
    def observe(
        cls, documents: ReadingEvidenceStorageDocumentInventory
    ) -> ReadingEvidenceStorageCollectionDigestInventory:
        """Observe exact completion evidence for all child collections."""
        if type(documents) is not ReadingEvidenceStorageDocumentInventory:
            raise TypeError("documents has an unsupported type")
        return cls(
            *(
                ReadingEvidenceStorageCollectionDigest.observe(
                    collection=collection,
                    documents=documents,
                )
                for collection in (
                    ReadingEvidenceStorageCollection.non_completion()
                )
            )
        )

    def __iter__(self) -> Iterator[ReadingEvidenceStorageCollectionDigest]:
        return iter(self._digests)

    def __len__(self) -> int:
        return len(self._digests)

    @property
    def total_document_count(self) -> int:
        """Return the exact aggregate child-document count."""
        return sum(value.document_count for value in self._digests)

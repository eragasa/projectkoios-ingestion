"""One immutable canonical document in an extraction read model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.storage.extraction.projection.collection import (
    ExtractionProjectionCollection,
)

_CONTENT_DIGEST_FIELD = "projection_content_sha256"


@dataclass(frozen=True, slots=True)
class ExtractionProjectionDocument(AbstractImmutableDataObject):
    """Retain one canonical backend-neutral projected document.

    Parameters
    ----------
    projection_document_id
        Stable identity of this projection member and its content.
    collection
        Logical read-model collection, independent of a physical store name.
    document_id
        Stable ``_id`` written by a materializer.
    publication_digest
        SHA-256 digest of the authoritative extraction payload.
    content_sha256
        Digest of projected fields before the digest marker is inserted.
    canonical_sha256
        Digest of the final canonical JSON including that marker.
    document_json
        Canonical immutable JSON materialized by storage adapters.
    contract_version
        Version of this projection-document contract.

    Notes
    -----
    ``content_sha256`` supports create-once conflict detection. The separate
    ``canonical_sha256`` covers every stored field and supports full-content
    inventories without relying on a document's own digest claim.
    """

    CONTRACT_NAME: ClassVar[str] = "extraction-projection-document"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_DOCUMENT_BYTES: ClassVar[int] = 15_000_000

    projection_document_id: str
    collection: ExtractionProjectionCollection
    document_id: str
    publication_digest: str
    content_sha256: str
    canonical_sha256: str
    document_json: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        collection: ExtractionProjectionCollection,
        value: dict[str, object],
    ) -> ExtractionProjectionDocument:
        """Create a canonical projection document from JSON-compatible fields.

        Parameters
        ----------
        collection
            Logical collection receiving the projected document.
        value
            Complete JSON-compatible fields, including ``_id`` and
            ``publication_digest`` but excluding the reserved content digest.

        Returns
        -------
        ExtractionProjectionDocument
            Immutable canonical projection member.

        Raises
        ------
        TypeError
            If the collection or document container has the wrong type.
        ValueError
            If identities, digests, reserved fields, or size bounds are
            invalid.
        """
        if not isinstance(collection, ExtractionProjectionCollection):
            raise TypeError("projection collection is invalid")
        if type(value) is not dict:
            raise TypeError("projected document must be a dictionary")
        document_id = value.get("_id")
        publication_digest = value.get("publication_digest")
        if type(document_id) is not str or not document_id:
            raise ValueError("projected document identity is invalid")
        if not SHA256Hash.is_canonical(publication_digest):
            raise ValueError("projected publication digest is invalid")
        if _CONTENT_DIGEST_FIELD in value:
            raise ValueError("projected content digest is reserved")
        projected = dict(value)
        # Hash the actual projected content before adding the marker. This
        # avoids a recursive digest while binding every domain field.
        content_sha256 = cls._digest(
            CanonicalJsonSerializer.serialize_text(projected)
        )
        projected[_CONTENT_DIGEST_FIELD] = content_sha256
        # Hash the final stored form separately. Inventory readers must compute
        # this digest from observed content rather than trusting the marker.
        serialized = CanonicalJsonSerializer.serialize_text(projected)
        canonical_sha256 = cls._digest(serialized)
        return cls(
            projection_document_id=stable_id(
                "extraction-projection-document",
                cls.CONTRACT_VERSION,
                collection.value,
                document_id,
                publication_digest,
                content_sha256,
                canonical_sha256,
            ),
            collection=collection,
            document_id=document_id,
            publication_digest=publication_digest,
            content_sha256=content_sha256,
            canonical_sha256=canonical_sha256,
            document_json=serialized,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported extraction-projection document")
        if not isinstance(self.collection, ExtractionProjectionCollection):
            raise TypeError("projection collection is invalid")
        if type(self.document_json) is not str or not self.document_json:
            raise ValueError("projected document JSON is invalid")
        if (
            len(self.document_json.encode("utf-8"))
            > self.MAXIMUM_DOCUMENT_BYTES
        ):
            raise ValueError("projected document exceeds its byte bound")
        try:
            value = json.loads(self.document_json)
        except json.JSONDecodeError as error:
            raise ValueError("projected document JSON is invalid") from error
        if (
            type(value) is not dict
            or CanonicalJsonSerializer.serialize_text(value)
            != self.document_json
        ):
            raise ValueError("projected document JSON is not canonical")
        if (
            value.get("_id") != self.document_id
            or value.get("publication_digest") != self.publication_digest
            or value.get(_CONTENT_DIGEST_FIELD) != self.content_sha256
        ):
            raise ValueError("projected document fields are inconsistent")
        base_value = dict(value)
        del base_value[_CONTENT_DIGEST_FIELD]
        expected_content = self._digest(
            CanonicalJsonSerializer.serialize_text(base_value)
        )
        expected_canonical = self._digest(self.document_json)
        if (
            type(self.document_id) is not str
            or not self.document_id
            or not SHA256Hash.is_canonical(self.publication_digest)
            or self.content_sha256 != expected_content
            or self.canonical_sha256 != expected_canonical
        ):
            raise ValueError("projected document digest is inconsistent")
        expected_id = stable_id(
            "extraction-projection-document",
            self.CONTRACT_VERSION,
            self.collection.value,
            self.document_id,
            self.publication_digest,
            self.content_sha256,
            self.canonical_sha256,
        )
        if self.projection_document_id != expected_id:
            raise ValueError("projection-document ID is inconsistent")

    @staticmethod
    def _digest(value: str) -> str:
        return SHA256Fingerprinter.fingerprint(content=value.encode("utf-8"))

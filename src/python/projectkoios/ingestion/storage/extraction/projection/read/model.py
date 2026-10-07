"""Immutable backend-neutral extraction read model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.projector.value import AbstractProjectionValue
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.storage.extraction.projection.document import (
    ExtractionProjectionDocument,
)


@dataclass(frozen=True, slots=True)
class ExtractionReadModel(AbstractProjectionValue):
    """Retain the complete rebuildable extraction projection value.

    Parameters
    ----------
    projection_id
        Stable identity over sources, configuration, schema, and member digest.
    source_evidence_ids
        Canonically ordered identities of all publication evidence.
    configuration_id
        Exact deterministic configuration used to derive the value.
    schema_id
        Logical schema required by a compatible materializer.
    canonical_sha256
        Aggregate digest over every projection member's content digest.
    documents
        Canonically ordered, identity-unique projection members.
    contract_version
        Version of this read-model contract.

    Notes
    -----
    The value contains no database handle, collection cursor, authority token,
    or mutable lookup. Any compatible materializer can rebuild its target from
    this value alone.
    """

    CONTRACT_NAME: ClassVar[str] = "extraction-read-model"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_DOCUMENTS: ClassVar[int] = 50_000_000

    projection_id: str
    source_evidence_ids: tuple[str, ...]
    configuration_id: str
    schema_id: str
    canonical_sha256: str
    documents: tuple[ExtractionProjectionDocument, ...]
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source_evidence_ids: tuple[str, ...],
        configuration_id: str,
        schema_id: str,
        documents: tuple[ExtractionProjectionDocument, ...],
    ) -> ExtractionReadModel:
        """Create a read model from canonical immutable members.

        Parameters
        ----------
        source_evidence_ids
            Ordered unique identities of the complete source evidence.
        configuration_id
            Identity of the complete deterministic configuration.
        schema_id
            Logical read-model schema identity.
        documents
            Ordered unique projected documents.

        Returns
        -------
        ExtractionReadModel
            Immutable aggregate projection value.

        Raises
        ------
        TypeError
            If projection members have the wrong concrete type.
        ValueError
            If ordering, uniqueness, schema, bounds, or identities are
            inconsistent.
        """
        members = cls._members(documents)
        # Aggregate compact member evidence rather than duplicating every JSON
        # document in the identity input. Each member digest already binds its
        # complete canonical content.
        digest = SHA256Fingerprinter.fingerprint(
            content=CanonicalJsonSerializer.serialize_text(members).encode(
                "utf-8"
            )
        )
        return cls(
            projection_id=stable_id(
                "extraction-read-model",
                cls.CONTRACT_VERSION,
                source_evidence_ids,
                configuration_id,
                schema_id,
                digest,
            ),
            source_evidence_ids=source_evidence_ids,
            configuration_id=configuration_id,
            schema_id=schema_id,
            canonical_sha256=digest,
            documents=documents,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported extraction read-model contract")
        if (
            not isinstance(self.source_evidence_ids, tuple)
            or not self.source_evidence_ids
            or self.source_evidence_ids
            != tuple(sorted(set(self.source_evidence_ids)))
        ):
            raise ValueError("read-model source identities are invalid")
        if type(self.configuration_id) is not str or not self.configuration_id:
            raise ValueError("read-model configuration identity is invalid")
        if type(self.schema_id) is not str or not self.schema_id:
            raise ValueError("read-model schema identity is invalid")
        if not isinstance(self.documents, tuple) or any(
            type(document) is not ExtractionProjectionDocument
            for document in self.documents
        ):
            raise TypeError("read-model documents are invalid")
        if not self.documents or len(self.documents) > self.MAXIMUM_DOCUMENTS:
            raise ValueError("read-model document count is out of bounds")
        keys = tuple(
            (document.collection.value, document.document_id)
            for document in self.documents
        )
        if keys != tuple(sorted(keys)):
            raise ValueError("read-model documents are not canonical")
        if len(keys) != len(set(keys)):
            raise ValueError("read-model document identities are not unique")
        digest = SHA256Fingerprinter.fingerprint(
            content=CanonicalJsonSerializer.serialize_text(
                self._members(self.documents)
            ).encode("utf-8")
        )
        if self.canonical_sha256 != digest:
            raise ValueError("read-model canonical digest is inconsistent")
        expected_id = stable_id(
            "extraction-read-model",
            self.CONTRACT_VERSION,
            self.source_evidence_ids,
            self.configuration_id,
            self.schema_id,
            digest,
        )
        if self.projection_id != expected_id:
            raise ValueError("read-model projection ID is inconsistent")

    @staticmethod
    def _members(
        documents: tuple[ExtractionProjectionDocument, ...],
    ) -> tuple[tuple[str, str, str, str, str], ...]:
        return tuple(
            (
                document.collection.value,
                document.document_id,
                document.publication_digest,
                document.content_sha256,
                document.canonical_sha256,
            )
            for document in documents
        )

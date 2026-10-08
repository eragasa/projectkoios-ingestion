"""Complete immutable backend-neutral reading-evidence read models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.projector.value import AbstractProjectionValue
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.inventory import (  # noqa: E501
    ReadingEvidenceStorageDocumentInventory,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.kind import (  # noqa: E501
    ReadingEvidenceStorageRecordKind,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.schema.version import (  # noqa: E501
    ReadingEvidenceStorageSchemaVersion,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceReadModel(AbstractProjectionValue):
    """Retain one complete rebuildable reading-evidence generation."""

    CONTRACT_NAME: ClassVar[str] = "reading-evidence-read-model"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    projection_id: str
    source_projection_result_id: ReadingEvidenceIdentity
    configuration_id: str
    schema_id: str
    schema_version: ReadingEvidenceStorageSchemaVersion
    generation_id: str
    evidence_document_id: ReadingEvidenceIdentity
    canonical_sha256: SHA256Hash
    documents: ReadingEvidenceStorageDocumentInventory
    contract_version: str = CONTRACT_VERSION

    @property
    def source_evidence_ids(self) -> tuple[str, ...]:  # type: ignore[override]
        """Return the sole canonical evidence-document source identity."""
        return (self.evidence_document_id.value,)

    @classmethod
    def create(
        cls,
        *,
        source_projection_result_id: ReadingEvidenceIdentity,
        configuration_id: str,
        schema_version: ReadingEvidenceStorageSchemaVersion,
        generation_id: str,
        evidence_document_id: ReadingEvidenceIdentity,
        documents: ReadingEvidenceStorageDocumentInventory,
    ) -> ReadingEvidenceReadModel:
        """Create one complete read model from canonical members."""
        members = cls._members(documents)
        digest = SHA256Fingerprinter.fingerprint(
            content=CanonicalJsonSerializer.serialize_bytes(members)
        )
        return cls(
            projection_id=stable_id(
                "reading-evidence-read-model",
                cls.CONTRACT_VERSION,
                source_projection_result_id.value,
                configuration_id,
                schema_version.schema_id,
                generation_id,
                evidence_document_id.value,
                digest,
            ),
            source_projection_result_id=source_projection_result_id,
            configuration_id=configuration_id,
            schema_id=schema_version.schema_id,
            schema_version=schema_version,
            generation_id=generation_id,
            evidence_document_id=evidence_document_id,
            canonical_sha256=digest,
            documents=documents,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported reading-evidence read model")
        if (
            type(self.source_projection_result_id)
            is not ReadingEvidenceIdentity
            or self.source_projection_result_id.kind
            is not ReadingEvidenceIdentityKind.PROJECTION_RESULT
        ):
            raise TypeError("source_projection_result_id has the wrong role")
        if type(self.configuration_id) is not str or not self.configuration_id:
            raise ValueError("configuration_id must be non-empty")
        if type(self.schema_version) is not ReadingEvidenceStorageSchemaVersion:
            raise TypeError("schema_version has an unsupported type")
        if self.schema_id != self.schema_version.schema_id:
            raise ValueError("schema_id differs from schema_version")
        if type(self.generation_id) is not str or not self.generation_id:
            raise ValueError("generation_id must be non-empty")
        if (
            type(self.evidence_document_id) is not ReadingEvidenceIdentity
            or self.evidence_document_id.kind
            is not ReadingEvidenceIdentityKind.EVIDENCE_DOCUMENT
        ):
            raise TypeError("evidence_document_id has the wrong role")
        if type(self.documents) is not ReadingEvidenceStorageDocumentInventory:
            raise TypeError("documents has an unsupported type")
        values = tuple(self.documents)
        if not values:
            raise ValueError("read model must contain documents")
        if any(
            value.schema_version != self.schema_version
            or value.generation_id != self.generation_id
            or value.evidence_document_id != self.evidence_document_id
            for value in values
        ):
            raise ValueError("read-model document scope differs")
        completions = self.documents.for_kind(
            ReadingEvidenceStorageRecordKind.COMPLETION
        )
        if len(completions) != 1:
            raise ValueError("read model requires one completion member")
        digest = SHA256Fingerprinter.fingerprint(
            content=CanonicalJsonSerializer.serialize_bytes(
                self._members(self.documents)
            )
        )
        if self.canonical_sha256 != digest:
            raise ValueError("read-model canonical digest is inconsistent")
        expected = stable_id(
            "reading-evidence-read-model",
            self.CONTRACT_VERSION,
            self.source_projection_result_id.value,
            self.configuration_id,
            self.schema_version.schema_id,
            self.generation_id,
            self.evidence_document_id.value,
            digest,
        )
        if self.projection_id != expected:
            raise ValueError("read-model projection identity is inconsistent")

    @staticmethod
    def _members(
        documents: ReadingEvidenceStorageDocumentInventory,
    ) -> tuple[tuple[str, str, str], ...]:
        return tuple(
            (
                value.kind.collection.value,
                value.document_id,
                value.canonical_sha256,
            )
            for value in documents
        )

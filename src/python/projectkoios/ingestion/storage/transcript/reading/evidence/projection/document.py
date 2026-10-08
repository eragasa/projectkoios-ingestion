"""Immutable backend-neutral reading-evidence storage documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.json.parser import JsonParser
from projectkoios.ingestion.json.serializer import JsonSerializer
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash
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
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)

_CONTENT_DIGEST_FIELD = "projection_content_sha256"


@dataclass(frozen=True, slots=True)
class ReadingEvidenceStorageDocument(AbstractImmutableDataObject):
    """Retain one canonical backend-neutral current-schema member."""

    CONTRACT_NAME: ClassVar[str] = "reading-evidence-storage-document"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    parser: ClassVar[JsonParser] = JsonParser(CanonicalJsonSerializer.limits)
    serializer: ClassVar[JsonSerializer] = JsonSerializer.canonical(
        limits=CanonicalJsonSerializer.limits
    )

    projection_document_id: str
    schema_version: ReadingEvidenceStorageSchemaVersion
    generation_id: str
    evidence_document_id: ReadingEvidenceIdentity
    kind: ReadingEvidenceStorageRecordKind
    document_id: str
    semantic_id: str
    content_sha256: SHA256Hash
    canonical_sha256: SHA256Hash
    document_json: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        schema_version: ReadingEvidenceStorageSchemaVersion,
        generation_id: str,
        evidence_document_id: ReadingEvidenceIdentity,
        kind: ReadingEvidenceStorageRecordKind,
        semantic_id: str,
        payload: JsonValue,
        maximum_document_bytes: int,
    ) -> ReadingEvidenceStorageDocument:
        """Create one canonical member from one strict JSON payload."""
        cls._validate_scope(
            schema_version=schema_version,
            generation_id=generation_id,
            evidence_document_id=evidence_document_id,
            kind=kind,
            semantic_id=semantic_id,
        )
        if (
            type(maximum_document_bytes) is not int
            or not 1
            <= maximum_document_bytes
            <= READING_EVIDENCE_LIMITS.maximum_single_record_bytes
        ):
            raise ValueError("storage document byte bound is invalid")
        document_id = stable_id(
            "reading-evidence-storage-record",
            cls.CONTRACT_VERSION,
            schema_version.schema_id,
            generation_id,
            evidence_document_id.value,
            kind.value,
            semantic_id,
        )
        projected: dict[str, JsonValue] = {
            "_id": document_id,
            "schema_id": schema_version.schema_id,
            "generation_id": generation_id,
            "evidence_document_id": evidence_document_id.value,
            "record_kind": kind.value,
            "semantic_id": semantic_id,
            "payload": payload,
        }
        content_text = cls.serializer.serialize_text(projected)
        content_sha256 = SHA256Fingerprinter.fingerprint(
            content=content_text.encode("utf-8")
        )
        projected[_CONTENT_DIGEST_FIELD] = content_sha256
        serialized = cls.serializer.serialize_text(projected)
        if len(serialized.encode("utf-8")) > maximum_document_bytes:
            raise ValueError("storage document exceeds its byte bound")
        canonical_sha256 = SHA256Fingerprinter.fingerprint(
            content=serialized.encode("utf-8")
        )
        return cls(
            projection_document_id=stable_id(
                "reading-evidence-storage-projection-document",
                cls.CONTRACT_VERSION,
                kind.collection.value,
                document_id,
                content_sha256,
                canonical_sha256,
            ),
            schema_version=schema_version,
            generation_id=generation_id,
            evidence_document_id=evidence_document_id,
            kind=kind,
            document_id=document_id,
            semantic_id=semantic_id,
            content_sha256=content_sha256,
            canonical_sha256=canonical_sha256,
            document_json=serialized,
        )

    @classmethod
    def from_document_json(
        cls,
        *,
        document_json: str,
        schema_version: ReadingEvidenceStorageSchemaVersion,
        maximum_document_bytes: int,
    ) -> ReadingEvidenceStorageDocument:
        """Reconstruct one member from exact observed canonical JSON."""
        if type(document_json) is not str or not document_json:
            raise ValueError("observed storage document JSON is invalid")
        encoded = document_json.encode("utf-8", errors="strict")
        if len(encoded) > maximum_document_bytes:
            raise ValueError("observed storage document exceeds its byte bound")
        value = cls.parser.parse_bytes(encoded)
        if type(value) is not dict:
            raise ValueError("observed storage document must be an object")
        required = {
            "_id",
            "schema_id",
            "generation_id",
            "evidence_document_id",
            "record_kind",
            "semantic_id",
            "payload",
            _CONTENT_DIGEST_FIELD,
        }
        if set(value) != required:
            raise ValueError("observed storage document fields differ")
        if value["schema_id"] != schema_version.schema_id:
            raise ValueError("observed storage schema differs")
        record_kind = cls._require_text(value["record_kind"], "record_kind")
        generation_id = cls._require_text(
            value["generation_id"], "generation_id"
        )
        evidence_identity = cls._require_text(
            value["evidence_document_id"], "evidence_document_id"
        )
        document_id = cls._require_text(value["_id"], "_id")
        semantic_id = cls._require_text(value["semantic_id"], "semantic_id")
        content_sha256 = value[_CONTENT_DIGEST_FIELD]
        kind = ReadingEvidenceStorageRecordKind(record_kind)
        evidence_document_id = ReadingEvidenceIdentity(
            kind=ReadingEvidenceIdentityKind.EVIDENCE_DOCUMENT,
            value=evidence_identity,
        )
        if not SHA256Hash.is_canonical(content_sha256):
            raise ValueError("observed content digest is invalid")
        canonical_sha256 = SHA256Fingerprinter.fingerprint(content=encoded)
        return cls(
            projection_document_id=stable_id(
                "reading-evidence-storage-projection-document",
                cls.CONTRACT_VERSION,
                kind.collection.value,
                document_id,
                content_sha256,
                canonical_sha256,
            ),
            schema_version=schema_version,
            generation_id=generation_id,
            evidence_document_id=evidence_document_id,
            kind=kind,
            document_id=document_id,
            semantic_id=semantic_id,
            content_sha256=SHA256Hash(content_sha256),
            canonical_sha256=canonical_sha256,
            document_json=document_json,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported storage document contract")
        self._validate_scope(
            schema_version=self.schema_version,
            generation_id=self.generation_id,
            evidence_document_id=self.evidence_document_id,
            kind=self.kind,
            semantic_id=self.semantic_id,
        )
        if type(self.document_json) is not str or not self.document_json:
            raise ValueError("storage document JSON must be non-empty")
        encoded = self.document_json.encode("utf-8", errors="strict")
        if len(encoded) > READING_EVIDENCE_LIMITS.maximum_single_record_bytes:
            raise ValueError("storage document exceeds its hard byte bound")
        value = self.parser.parse_bytes(encoded)
        if type(value) is not dict:
            raise ValueError("storage document JSON root must be an object")
        if self.serializer.serialize_text(value) != self.document_json:
            raise ValueError("storage document JSON must be canonical")
        expected_fields = {
            "_id",
            "schema_id",
            "generation_id",
            "evidence_document_id",
            "record_kind",
            "semantic_id",
            "payload",
            _CONTENT_DIGEST_FIELD,
        }
        if set(value) != expected_fields:
            raise ValueError("storage document fields differ from schema")
        if (
            value["_id"] != self.document_id
            or value["schema_id"] != self.schema_version.schema_id
            or value["generation_id"] != self.generation_id
            or value["evidence_document_id"] != self.evidence_document_id.value
            or value["record_kind"] != self.kind.value
            or value["semantic_id"] != self.semantic_id
            or value[_CONTENT_DIGEST_FIELD] != self.content_sha256
        ):
            raise ValueError("storage document fields are inconsistent")
        base = dict(value)
        del base[_CONTENT_DIGEST_FIELD]
        expected_content = SHA256Fingerprinter.fingerprint(
            content=self.serializer.serialize_bytes(base)
        )
        expected_canonical = SHA256Fingerprinter.fingerprint(content=encoded)
        if (
            not SHA256Hash.is_canonical(self.content_sha256)
            or not SHA256Hash.is_canonical(self.canonical_sha256)
            or self.content_sha256 != expected_content
            or self.canonical_sha256 != expected_canonical
        ):
            raise ValueError("storage document digest is inconsistent")
        expected_document_id = stable_id(
            "reading-evidence-storage-record",
            self.CONTRACT_VERSION,
            self.schema_version.schema_id,
            self.generation_id,
            self.evidence_document_id.value,
            self.kind.value,
            self.semantic_id,
        )
        if self.document_id != expected_document_id:
            raise ValueError("storage document identity is inconsistent")
        expected_projection_id = stable_id(
            "reading-evidence-storage-projection-document",
            self.CONTRACT_VERSION,
            self.kind.collection.value,
            self.document_id,
            self.content_sha256,
            self.canonical_sha256,
        )
        if self.projection_document_id != expected_projection_id:
            raise ValueError("projection-document identity is inconsistent")

    def payload(self) -> JsonValue:
        """Return the strictly parsed semantic payload."""
        value = self.parser.parse_text(self.document_json)
        if type(value) is not dict:
            raise ValueError("storage document JSON root must be an object")
        return value["payload"]

    @staticmethod
    def _require_text(value: JsonValue, name: str) -> str:
        if type(value) is not str or not value:
            raise ValueError(f"observed {name} is invalid")
        return value

    @staticmethod
    def _validate_scope(
        *,
        schema_version: ReadingEvidenceStorageSchemaVersion,
        generation_id: str,
        evidence_document_id: ReadingEvidenceIdentity,
        kind: ReadingEvidenceStorageRecordKind,
        semantic_id: str,
    ) -> None:
        if type(schema_version) is not ReadingEvidenceStorageSchemaVersion:
            raise TypeError("schema_version has an unsupported type")
        for value, name, maximum in (
            (generation_id, "generation_id", 256),
            (semantic_id, "semantic_id", 1_024),
        ):
            if type(value) is not str or not value:
                raise ValueError(f"{name} must be non-empty")
            if len(value.encode("utf-8", errors="strict")) > maximum:
                raise ValueError(f"{name} exceeds its limit")
        if (
            type(evidence_document_id) is not ReadingEvidenceIdentity
            or evidence_document_id.kind
            is not ReadingEvidenceIdentityKind.EVIDENCE_DOCUMENT
        ):
            raise TypeError("evidence_document_id has the wrong role")
        if not isinstance(kind, ReadingEvidenceStorageRecordKind):
            raise TypeError("storage record kind has an unsupported type")

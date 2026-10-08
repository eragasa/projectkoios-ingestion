"""Thin MongoDB reader for backend-neutral reading-evidence read models."""

from __future__ import annotations

from typing import Any, ClassVar

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.configuration import (  # noqa: E501
    MongoReadingEvidenceConfiguration,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.error import (  # noqa: E501
    MongoReadingEvidenceError,
)
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.storage.transcript.reading.evidence.completion.manifest import (  # noqa: E501
    ReadingEvidenceCompletionManifest,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.json.contract import (  # noqa: E501
    ReadingEvidenceStorageJsonContract,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.target import (  # noqa: E501
    ReadingEvidenceMaterializationTarget,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.collection import (  # noqa: E501
    ReadingEvidenceStorageCollection,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.document import (  # noqa: E501
    ReadingEvidenceStorageDocument,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.inventory import (  # noqa: E501
    ReadingEvidenceStorageDocumentInventory,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.kind import (  # noqa: E501
    ReadingEvidenceStorageRecordKind,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.read.model import (  # noqa: E501
    ReadingEvidenceReadModel,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.schema.version import (  # noqa: E501
    ReadingEvidenceStorageSchemaVersion,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.source.reader import (  # noqa: E501
    ReadingEvidenceReadModelReader,
)
from projectkoios.ingestion.transcript.reading.evidence.source.request import (
    ReadingEvidenceSourceRequest,
)
from pymongo.database import Database
from pymongo.errors import PyMongoError

MongoDocument = dict[str, Any]


class MongoReadingEvidenceReadModelReader(ReadingEvidenceReadModelReader):
    """Read one exact completed current generation from MongoDB."""

    __slots__ = (
        "database",
        "configured_target",
        "configuration",
        "generation_id",
        "source_id",
    )

    IMPLEMENTATION_ID: ClassVar[str] = (
        "mongodb-reading-evidence-read-model-reader:1.0"
    )

    def __init__(
        self,
        *,
        database: Database[MongoDocument],
        configured_target: ReadingEvidenceMaterializationTarget,
        configuration: MongoReadingEvidenceConfiguration,
        generation_id: str,
    ) -> None:
        if type(configured_target) is not ReadingEvidenceMaterializationTarget:
            raise TypeError("configured_target has an unsupported type")
        if type(configuration) is not MongoReadingEvidenceConfiguration:
            raise TypeError("configuration has an unsupported type")
        if type(generation_id) is not str or not generation_id:
            raise ValueError("generation_id must be non-empty")
        if len(generation_id.encode("utf-8", errors="strict")) > 256:
            raise ValueError("generation_id exceeds its limit")
        if database.name != configured_target.store_name:
            raise ValueError(
                "configured target differs from database capability"
            )
        if (
            configured_target.schema_id
            != configuration.materialization.schema_id
        ):
            raise ValueError("configured target and storage schema differ")
        self.database = database
        self.configured_target = configured_target
        self.configuration = configuration
        self.generation_id = generation_id
        self.source_id = stable_id(
            "mongodb-reading-evidence-source",
            configured_target.target_id,
            configuration.configuration_id,
            generation_id,
        )

    @property
    def implementation_id(self) -> str:
        """Return the exact concrete reader implementation identity."""
        return self.IMPLEMENTATION_ID

    def read(
        self, *, request: ReadingEvidenceSourceRequest
    ) -> ReadingEvidenceReadModel:
        """Read one bounded generation only after requiring completion."""
        if type(request) is not ReadingEvidenceSourceRequest:
            raise TypeError("request has an unsupported type")
        if request.provider_source_id != self.source_id:
            raise MongoReadingEvidenceError(
                code="source_identity_mismatch",
                message="requested source differs from configured source",
            )
        schema = ReadingEvidenceStorageSchemaVersion.current()
        names = self.configuration.materialization.names()
        self._require_indexes(names=tuple(names.values()))
        scope: MongoDocument = {
            "schema_id": schema.schema_id,
            "generation_id": self.generation_id,
            "evidence_document_id": request.document_id.value,
        }
        completion_values = self._bounded_find(
            collection_name=names[ReadingEvidenceStorageCollection.COMPLETIONS],
            query=scope,
            maximum_count=1,
        )
        if len(completion_values) != 1:
            raise MongoReadingEvidenceError(
                code="completion_missing",
                message="exactly one completion member is required",
            )
        completion = self._member(completion_values[0], schema)
        if completion.kind is not ReadingEvidenceStorageRecordKind.COMPLETION:
            raise MongoReadingEvidenceError(
                code="collection_role_mismatch",
                message="stored completion member has the wrong role",
            )
        manifest = ReadingEvidenceStorageJsonContract().decode_as(
            completion.payload(), ReadingEvidenceCompletionManifest
        )
        if (
            completion.semantic_id != manifest.manifest_id
            or manifest.schema_version != schema
            or manifest.generation_id != self.generation_id
            or manifest.evidence_document_id != request.document_id
            or manifest.projection_result_id != request.projection_result_id
            or manifest.inventory_id != request.inventory_id
        ):
            raise MongoReadingEvidenceError(
                code="completion_mismatch",
                message="completion member differs from requested source",
            )
        expected_counts = {
            value.collection: value.document_count
            for value in manifest.collections
        }
        expected_total = 1 + sum(expected_counts.values())
        if expected_total > request.maximum_provider_record_count:
            raise MongoReadingEvidenceError(
                code="record_limit",
                message="completed generation exceeds requested record bound",
            )
        members: list[ReadingEvidenceStorageDocument] = [completion]
        for collection in ReadingEvidenceStorageCollection.non_completion():
            values = self._bounded_find(
                collection_name=names[collection],
                query=scope,
                maximum_count=expected_counts[collection],
            )
            if len(values) != expected_counts[collection]:
                raise MongoReadingEvidenceError(
                    code="collection_count_mismatch",
                    message="stored collection count differs from completion",
                )
            for value in values:
                member = self._member(value, schema)
                if member.kind.collection is not collection:
                    raise MongoReadingEvidenceError(
                        code="collection_role_mismatch",
                        message="stored member is in the wrong collection",
                    )
                members.append(member)
        members.sort(
            key=lambda value: (value.kind.collection.value, value.document_id)
        )
        inventory = ReadingEvidenceStorageDocumentInventory(*members)
        return ReadingEvidenceReadModel.create(
            source_projection_result_id=manifest.projection_result_id,
            configuration_id=manifest.storage_configuration_id,
            schema_version=schema,
            generation_id=self.generation_id,
            evidence_document_id=request.document_id,
            documents=inventory,
        )

    def _require_indexes(self, *, names: tuple[str, ...]) -> None:
        try:
            for name in names:
                value = (
                    self.database[name]
                    .index_information()
                    .get(self.configuration.scope_index_name)
                )
                if value is None or not self.configuration.matches_scope_index(
                    value
                ):
                    raise MongoReadingEvidenceError(
                        code="index_not_ready",
                        message=(
                            "MongoDB reading-evidence scope index is absent"
                        ),
                    )
        except MongoReadingEvidenceError:
            raise
        except PyMongoError as error:
            raise MongoReadingEvidenceError(
                code="index_read_failed",
                message="MongoDB reading-evidence index inspection failed",
            ) from error

    def _bounded_find(
        self,
        *,
        collection_name: str,
        query: MongoDocument,
        maximum_count: int,
    ) -> list[MongoDocument]:
        try:
            cursor = (
                self.database[collection_name]
                .find(query)
                .sort("_id", 1)
                .limit(maximum_count + 1)
                .batch_size(self.configuration.cursor_batch_size)
            )
            values = list(cursor)
        except PyMongoError as error:
            raise MongoReadingEvidenceError(
                code="read_failed",
                message="MongoDB reading-evidence read failed",
            ) from error
        if len(values) > maximum_count:
            raise MongoReadingEvidenceError(
                code="collection_extra_records",
                message="stored collection contains unexpected records",
            )
        return values

    def _member(
        self,
        value: MongoDocument,
        schema: ReadingEvidenceStorageSchemaVersion,
    ) -> ReadingEvidenceStorageDocument:
        try:
            serialized = CanonicalJsonSerializer.serialize_text(value)
            return ReadingEvidenceStorageDocument.from_document_json(
                document_json=serialized,
                schema_version=schema,
                maximum_document_bytes=(
                    self.configuration.materialization.maximum_document_bytes
                ),
            )
        except (TypeError, ValueError) as error:
            raise MongoReadingEvidenceError(
                code="stored_document_invalid",
                message="stored MongoDB member is not current canonical JSON",
            ) from error

"""Thin MongoDB materializer for neutral reading-evidence read models."""

from __future__ import annotations

from typing import Any, ClassVar

from bson import BSON
from bson.errors import InvalidDocument
from projectkoios.ingestion.base.materializer.identity.error import (
    MaterializationIdentityError,
)
from projectkoios.ingestion.base.materializer.identity.model import (
    MaterializerIdentity,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.configuration import (  # noqa: E501
    MongoReadingEvidenceConfiguration,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.error import (  # noqa: E501
    MongoReadingEvidenceError,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.actionizer import (  # noqa: E501
    ReadingEvidenceMaterializer,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.configuration import (  # noqa: E501
    ReadingEvidenceMaterializationConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.evidence import (  # noqa: E501
    ReadingEvidenceMaterializationCollectionEvidence,
    ReadingEvidenceMaterializationCollectionEvidenceInventory,
    ReadingEvidenceMaterializationEvidence,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.target import (  # noqa: E501
    ReadingEvidenceMaterializationTarget,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.collection import (  # noqa: E501
    ReadingEvidenceStorageCollection,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.kind import (  # noqa: E501
    ReadingEvidenceStorageRecordKind,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.read.model import (  # noqa: E501
    ReadingEvidenceReadModel,
)
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

MongoDocument = dict[str, Any]


class MongoReadingEvidenceMaterializer(ReadingEvidenceMaterializer):
    """Create or exactly replay neutral projection members in MongoDB."""

    __slots__ = ("database", "configured_target", "mongo_configuration")

    AUTHORITY_REQUIREMENT: ClassVar[str] = "reading_evidence_projection_write"
    authority_requirement = AUTHORITY_REQUIREMENT
    identity = MaterializerIdentity.create(
        name="mongodb-reading-evidence-materializer",
        version="1.0",
        projection_contract=ReadingEvidenceReadModel.CONTRACT_NAME,
        target_contract=ReadingEvidenceMaterializationTarget.CONTRACT_NAME,
        configuration_contract=(
            ReadingEvidenceMaterializationConfiguration.CONTRACT_NAME
        ),
        evidence_contract=ReadingEvidenceMaterializationEvidence.CONTRACT_NAME,
        schema_id="projectkoios-reading-evidence-storage:v1",
        authority_requirement=AUTHORITY_REQUIREMENT,
    )

    _ORDER: ClassVar[dict[ReadingEvidenceStorageCollection, int]] = {
        ReadingEvidenceStorageCollection.PRODUCERS: 0,
        ReadingEvidenceStorageCollection.REFERENCES: 1,
        ReadingEvidenceStorageCollection.LIMITATIONS: 2,
        ReadingEvidenceStorageCollection.BLOCKS: 3,
        ReadingEvidenceStorageCollection.PAGES: 4,
        ReadingEvidenceStorageCollection.DOCUMENTS: 5,
        ReadingEvidenceStorageCollection.COMPLETIONS: 6,
    }

    def __init__(
        self,
        *,
        database: Database[MongoDocument],
        configured_target: ReadingEvidenceMaterializationTarget,
        configuration: MongoReadingEvidenceConfiguration,
    ) -> None:
        if type(configured_target) is not ReadingEvidenceMaterializationTarget:
            raise TypeError("configured_target has an unsupported type")
        if type(configuration) is not MongoReadingEvidenceConfiguration:
            raise TypeError("configuration has an unsupported type")
        if database.name != configured_target.store_name:
            raise MaterializationIdentityError(
                "configured target store differs from database capability"
            )
        if (
            configured_target.schema_id
            != configuration.materialization.schema_id
        ):
            raise MaterializationIdentityError(
                "configured target and physical schema differ"
            )
        self.database = database
        self.configured_target = configured_target
        self.mongo_configuration = configuration

    def materialize(
        self,
        *,
        projection: ReadingEvidenceReadModel,
        target: ReadingEvidenceMaterializationTarget,
        configuration: ReadingEvidenceMaterializationConfiguration,
        authority_id: str,
    ) -> ReadingEvidenceMaterializationEvidence:
        """Write children before the completion member with exact replay."""
        if target != self.configured_target:
            raise MaterializationIdentityError(
                "requested target differs from configured capability"
            )
        if configuration != self.mongo_configuration.materialization:
            raise MaterializationIdentityError(
                "requested mapping differs from configured mapping"
            )
        outcomes = {
            collection: [0, 0]
            for collection in ReadingEvidenceStorageCollection
        }
        ordered = sorted(
            projection.documents,
            key=lambda value: (
                self._ORDER[value.kind.collection],
                value.document_id,
            ),
        )
        if ordered[-1].kind is not ReadingEvidenceStorageRecordKind.COMPLETION:
            raise MongoReadingEvidenceError(
                code="completion_order",
                message="completion member is not last",
            )
        names = configuration.names()
        for member in ordered:
            value = member.parser.parse_text(member.document_json)
            if type(value) is not dict:
                raise MongoReadingEvidenceError(
                    code="projection_document_invalid",
                    message="projected member is not an object",
                )
            try:
                encoded = BSON.encode(value)
            except InvalidDocument as error:
                raise MongoReadingEvidenceError(
                    code="bson_invalid",
                    message="projected member is not valid BSON",
                ) from error
            if len(encoded) > configuration.maximum_document_bytes:
                raise MongoReadingEvidenceError(
                    code="bson_byte_limit",
                    message="projected member exceeds BSON byte bound",
                )
            created = self._create_once(
                collection_name=names[member.kind.collection],
                value=value,
            )
            outcomes[member.kind.collection][0 if created else 1] += 1
        collection_evidence = (
            ReadingEvidenceMaterializationCollectionEvidenceInventory(
                *(
                    ReadingEvidenceMaterializationCollectionEvidence(
                        collection=collection,
                        created_count=outcomes[collection][0],
                        unchanged_count=outcomes[collection][1],
                    )
                    for collection in ReadingEvidenceStorageCollection
                )
            )
        )
        return ReadingEvidenceMaterializationEvidence(
            projection_id=projection.projection_id,
            target_id=target.target_id,
            configuration_id=configuration.configuration_id,
            authority_id=authority_id,
            projected_document_count=len(projection.documents),
            collections=collection_evidence,
        )

    def _create_once(
        self, *, collection_name: str, value: MongoDocument
    ) -> bool:
        document_id = value.get("_id")
        if type(document_id) is not str or not document_id:
            raise MongoReadingEvidenceError(
                code="document_identity_invalid",
                message="projected member identity is invalid",
            )
        collection = self.database[collection_name]
        try:
            existing = collection.find_one({"_id": document_id})
            if existing is not None:
                if existing != value:
                    raise MongoReadingEvidenceError(
                        code="identity_conflict",
                        message="existing member content differs",
                    )
                return False
            collection.insert_one(value)
            return True
        except MongoReadingEvidenceError:
            raise
        except DuplicateKeyError as error:
            existing = collection.find_one({"_id": document_id})
            if existing == value:
                return False
            raise MongoReadingEvidenceError(
                code="identity_conflict",
                message="concurrent member content differs",
            ) from error
        except PyMongoError as error:
            raise MongoReadingEvidenceError(
                code="write_failed",
                message="MongoDB reading-evidence write failed",
            ) from error

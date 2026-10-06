"""MongoDB materializer for immutable extraction read models."""

from __future__ import annotations

import json
from typing import Any, ClassVar

from bson import BSON
from bson.errors import InvalidDocument
from projectkoios.ingestion.base.materializer.identity.error import (
    MaterializationIdentityError,
)
from projectkoios.ingestion.base.materializer.identity.model import (
    MaterializerIdentity,
)
from projectkoios.ingestion.integrations.mongodb.extraction.materialization.error import (  # noqa: E501
    MongoExtractionProjectionMaterializationError,
)
from projectkoios.ingestion.storage.extraction.materialization.configuration import (  # noqa: E501
    ExtractionProjectionMaterializationConfiguration,
)
from projectkoios.ingestion.storage.extraction.materialization.evidence.collection import (  # noqa: E501
    ExtractionProjectionMaterializationCollectionEvidence,
)
from projectkoios.ingestion.storage.extraction.materialization.evidence.model import (  # noqa: E501
    ExtractionProjectionMaterializationEvidence,
)
from projectkoios.ingestion.storage.extraction.materialization.materializer import (  # noqa: E501
    AbstractExtractionProjectionMaterializer,
)
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.collection import (
    ExtractionProjectionCollection,
)
from projectkoios.ingestion.storage.extraction.projection.read.model import (
    ExtractionReadModel,
)
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

MongoDocument = dict[str, Any]


class MongoExtractionProjectionMaterializer(
    AbstractExtractionProjectionMaterializer
):
    """Apply canonical extraction read models to one MongoDB target.

    Parameters
    ----------
    database
        Explicit MongoDB database capability used for writes.
    configured_target
        Exact deployment/database/schema/slot identity represented by that
        capability.

    Notes
    -----
    This class performs only effectful materialization. It does not read the
    authoritative journal, select records, project payloads, grant authority,
    create indexes, inventory target state, or retry failures.
    """

    __slots__ = ("database", "configured_target")

    AUTHORITY_REQUIREMENT: ClassVar[str] = "extraction_projection_write"
    authority_requirement = AUTHORITY_REQUIREMENT
    projection_type = ExtractionReadModel
    target_type = ExtractionProjectionTargetIdentity
    configuration_type = ExtractionProjectionMaterializationConfiguration
    evidence_type = ExtractionProjectionMaterializationEvidence
    identity = MaterializerIdentity.create(
        name="mongodb-extraction-projection-materializer",
        version="1.0",
        projection_contract=ExtractionReadModel.CONTRACT_NAME,
        target_contract=ExtractionProjectionTargetIdentity.CONTRACT_NAME,
        configuration_contract=(
            ExtractionProjectionMaterializationConfiguration.CONTRACT_NAME
        ),
        evidence_contract=(
            ExtractionProjectionMaterializationEvidence.CONTRACT_NAME
        ),
        schema_id="extraction-read-model-v1",
        authority_requirement=AUTHORITY_REQUIREMENT,
    )

    _ORDER: ClassVar[dict[ExtractionProjectionCollection, int]] = {
        ExtractionProjectionCollection.BLOCKS: 0,
        ExtractionProjectionCollection.PAGES: 1,
        ExtractionProjectionCollection.WARNINGS: 2,
        ExtractionProjectionCollection.MANIFESTS: 3,
        ExtractionProjectionCollection.DOCUMENTS: 4,
    }

    def __init__(
        self,
        *,
        database: Database[MongoDocument],
        configured_target: ExtractionProjectionTargetIdentity,
    ) -> None:
        if type(configured_target) is not ExtractionProjectionTargetIdentity:
            raise TypeError("configured_target has the wrong contract")
        if database.name != configured_target.database_name:
            raise MaterializationIdentityError(
                "configured target database differs from the capability"
            )
        self.database = database
        self.configured_target = configured_target

    def materialize(
        self,
        *,
        projection: ExtractionReadModel,
        target: ExtractionProjectionTargetIdentity,
        configuration: ExtractionProjectionMaterializationConfiguration,
        authority_id: str,
    ) -> ExtractionProjectionMaterializationEvidence:
        """Write one read model using create-once semantics.

        Parameters
        ----------
        projection
            Complete immutable extraction read model.
        target
            Exact target identity bound by the request.
        configuration
            Complete physical collection mapping and BSON byte bound.
        authority_id
            Exact authority identity bound by the request.

        Returns
        -------
        ExtractionProjectionMaterializationEvidence
            Per-collection and aggregate created/unchanged counts.

        Raises
        ------
        MaterializationIdentityError
            If the requested target differs from the configured capability.
        MongoExtractionProjectionMaterializationError
            If BSON encoding, document bounds, identity consistency, or the
            database write fails.

        Notes
        -----
        The read model's canonical sort order exists for identity stability.
        Materialization uses dependency order so root completion documents are
        never visible before their child documents.
        """
        if target != self.configured_target:
            raise MaterializationIdentityError(
                "requested target differs from the configured target"
            )
        collections = self._collections(configuration)
        outcomes = {
            collection: [0, 0] for collection in ExtractionProjectionCollection
        }
        ordered = sorted(
            projection.documents,
            key=lambda document: (
                self._ORDER[document.collection],
                document.document_id,
            ),
        )
        for projected in ordered:
            try:
                value = json.loads(projected.document_json)
            except json.JSONDecodeError as error:
                raise MongoExtractionProjectionMaterializationError(
                    code="projection_document_invalid",
                    message="projected document JSON is invalid",
                ) from error
            if type(value) is not dict:
                raise MongoExtractionProjectionMaterializationError(
                    code="projection_document_invalid",
                    message="projected document is not an object",
                )
            created = self._replace_create_once(
                collection_name=collections[projected.collection],
                value=value,
                content_sha256=projected.content_sha256,
                maximum_document_bytes=configuration.maximum_document_bytes,
            )
            outcomes[projected.collection][0 if created else 1] += 1

        collection_evidence = tuple(
            ExtractionProjectionMaterializationCollectionEvidence.create(
                collection=collection,
                created_document_count=outcomes[collection][0],
                unchanged_document_count=outcomes[collection][1],
            )
            for collection in ExtractionProjectionCollection
        )
        return ExtractionProjectionMaterializationEvidence.create(
            projection_id=projection.projection_id,
            target_id=target.target_id,
            configuration_id=configuration.configuration_id,
            authority_id=authority_id,
            projected_document_count=len(projection.documents),
            collections=collection_evidence,
        )

    @staticmethod
    def _collections(
        configuration: ExtractionProjectionMaterializationConfiguration,
    ) -> dict[ExtractionProjectionCollection, str]:
        return {
            ExtractionProjectionCollection.DOCUMENTS: (
                configuration.documents_collection
            ),
            ExtractionProjectionCollection.PAGES: (
                configuration.pages_collection
            ),
            ExtractionProjectionCollection.BLOCKS: (
                configuration.blocks_collection
            ),
            ExtractionProjectionCollection.WARNINGS: (
                configuration.warnings_collection
            ),
            ExtractionProjectionCollection.MANIFESTS: (
                configuration.manifests_collection
            ),
        }

    def _replace_create_once(
        self,
        *,
        collection_name: str,
        value: MongoDocument,
        content_sha256: str,
        maximum_document_bytes: int,
    ) -> bool:
        """Replace exact prior content or create one new document.

        The filter binds both the stable document identity and projected
        content digest. A different projection with the same ``_id`` reaches
        MongoDB's unique-key conflict instead of silently overwriting content.
        """
        try:
            encoded = BSON.encode(value)
            if len(encoded) > maximum_document_bytes:
                raise MongoExtractionProjectionMaterializationError(
                    code="projection_document_too_large",
                    message="MongoDB projection document is too large",
                )
            result = self.database[collection_name].replace_one(
                {
                    "_id": value["_id"],
                    "projection_content_sha256": content_sha256,
                },
                value,
                upsert=True,
            )
            return result.upserted_id is not None
        except InvalidDocument as error:
            raise MongoExtractionProjectionMaterializationError(
                code="projection_document_invalid",
                message="MongoDB projection document is invalid",
            ) from error
        except DuplicateKeyError as error:
            raise MongoExtractionProjectionMaterializationError(
                code="projection_identity_conflict",
                message="MongoDB projection identity has conflicting content",
            ) from error
        except PyMongoError as error:
            raise MongoExtractionProjectionMaterializationError(
                code="projection_write_failed",
                message="MongoDB extraction projection failed",
            ) from error

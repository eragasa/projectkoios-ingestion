"""Effectful MongoDB materializer for pure extraction read models."""

from __future__ import annotations

import json
from typing import Any, ClassVar

from bson import BSON
from bson.errors import InvalidDocument
from projectkoios.ingestion.integrations.mongodb.extraction.materialization_error import (  # noqa: E501
    MongoExtractionProjectionMaterializationError,
)
from projectkoios.ingestion.storage.extraction.projection.collection import (
    ExtractionProjectionCollection,
)
from projectkoios.ingestion.storage.extraction.projection.read_model import (
    ExtractionReadModel,
)
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

MongoDocument = dict[str, Any]


class MongoExtractionProjectionMaterializer:
    """Materialize canonical extraction read-model documents in MongoDB.

    Parameters
    ----------
    database
        Explicit MongoDB database target supplied by the adapter owner.

    Notes
    -----
    This class performs only effectful materialization. It does not read the
    authoritative journal, choose records, project payloads, authorize access,
    create indexes, inventory target state, or retry failures.
    """

    DOCUMENTS: ClassVar[str] = "extraction_documents"
    PAGES: ClassVar[str] = "extraction_pages"
    BLOCKS: ClassVar[str] = "extraction_blocks"
    WARNINGS: ClassVar[str] = "extraction_warnings"
    MANIFESTS: ClassVar[str] = "extraction_manifests"
    MAX_DOCUMENT_BYTES: ClassVar[int] = 15_000_000
    SUPPORTED_SCHEMA_ID: ClassVar[str] = "extraction-read-model-v1"

    _COLLECTIONS: ClassVar[dict[ExtractionProjectionCollection, str]] = {
        ExtractionProjectionCollection.DOCUMENTS: DOCUMENTS,
        ExtractionProjectionCollection.PAGES: PAGES,
        ExtractionProjectionCollection.BLOCKS: BLOCKS,
        ExtractionProjectionCollection.WARNINGS: WARNINGS,
        ExtractionProjectionCollection.MANIFESTS: MANIFESTS,
    }
    _ORDER: ClassVar[dict[ExtractionProjectionCollection, int]] = {
        ExtractionProjectionCollection.BLOCKS: 0,
        ExtractionProjectionCollection.PAGES: 1,
        ExtractionProjectionCollection.WARNINGS: 2,
        ExtractionProjectionCollection.MANIFESTS: 3,
        ExtractionProjectionCollection.DOCUMENTS: 4,
    }

    def __init__(self, *, database: Database[MongoDocument]) -> None:
        self.database = database

    def materialize(self, *, read_model: ExtractionReadModel) -> int:
        """Write one pure read model using create-once semantics.

        Parameters
        ----------
        read_model
            Complete immutable value produced by the extraction projector.

        Returns
        -------
        int
            Number of newly created root completion documents. Exact replay
            returns zero.

        Raises
        ------
        TypeError
            If ``read_model`` has the wrong concrete type.
        MongoExtractionProjectionMaterializationError
            If BSON encoding, document bounds, identity consistency, or the
            database write fails.

        Notes
        -----
        The materializer rejects unsupported schema identities before opening
        a collection. Child collections are then written before manifests and
        root completion documents. Consumers can ignore interrupted projection
        by requiring ``publication_state=complete`` on the root document.
        """
        if type(read_model) is not ExtractionReadModel:
            raise TypeError("read_model must be an ExtractionReadModel")
        if read_model.schema_id != self.SUPPORTED_SCHEMA_ID:
            raise MongoExtractionProjectionMaterializationError(
                code="projection_schema_unsupported",
                message="MongoDB materializer does not support this schema",
            )
        created_roots = 0
        # The read model's canonical sort order exists for identity stability.
        # Materialization uses a separate dependency order so the root
        # completion marker is never visible before its children.
        ordered = sorted(
            read_model.documents,
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
                collection_name=self._COLLECTIONS[projected.collection],
                value=value,
                content_sha256=projected.content_sha256,
            )
            if projected.collection is ExtractionProjectionCollection.DOCUMENTS:
                created_roots += int(created)
        return created_roots

    def _replace_create_once(
        self,
        *,
        collection_name: str,
        value: MongoDocument,
        content_sha256: str,
    ) -> bool:
        """Replace exact prior content or create one new document.

        The filter binds both the stable document identity and projected
        content digest. A different projection with the same ``_id`` reaches
        MongoDB's unique-key conflict instead of silently overwriting content.
        """
        try:
            encoded = BSON.encode(value)
            if len(encoded) > self.MAX_DOCUMENT_BYTES:
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

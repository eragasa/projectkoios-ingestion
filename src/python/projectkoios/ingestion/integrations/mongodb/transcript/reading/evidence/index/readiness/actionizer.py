"""MongoDB reading-evidence scope-index readiness action."""

from __future__ import annotations

from typing import Any, ClassVar

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.error import (  # noqa: E501
    MongoReadingEvidenceError,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.index.readiness.request import (  # noqa: E501
    MongoReadingEvidenceIndexReadinessRequest,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.index.readiness.result import (  # noqa: E501
    MongoReadingEvidenceIndexReadinessResult,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.target import (  # noqa: E501
    ReadingEvidenceMaterializationTarget,
)
from pymongo.database import Database
from pymongo.errors import PyMongoError

MongoDocument = dict[str, Any]


class MongoReadingEvidenceIndexReadinessActionizer(
    DataObjectActionizer[
        MongoReadingEvidenceIndexReadinessRequest,
        MongoReadingEvidenceIndexReadinessResult,
    ]
):
    """Create or exactly verify every configured MongoDB scope index."""

    __slots__ = ("database", "configured_target")

    AUTHORITY_REQUIREMENT: ClassVar[str] = (
        "reading_evidence_projection_index_write"
    )

    def __init__(
        self,
        *,
        database: Database[MongoDocument],
        configured_target: ReadingEvidenceMaterializationTarget,
    ) -> None:
        if type(configured_target) is not ReadingEvidenceMaterializationTarget:
            raise TypeError("configured_target has an unsupported type")
        if database.name != configured_target.store_name:
            raise ValueError(
                "configured target differs from database capability"
            )
        self.database = database
        self.configured_target = configured_target

    def action(
        self, *, request: MongoReadingEvidenceIndexReadinessRequest
    ) -> MongoReadingEvidenceIndexReadinessResult:
        """Create missing indexes and reject conflicting named definitions."""
        if type(request) is not MongoReadingEvidenceIndexReadinessRequest:
            raise TypeError("request has an unsupported type")
        if request.target != self.configured_target:
            raise ValueError(
                "requested target differs from configured capability"
            )
        created_count = 0
        unchanged_count = 0
        try:
            for name in request.configuration.materialization.names().values():
                collection = self.database[name]
                indexes = collection.index_information()
                existing = indexes.get(request.configuration.scope_index_name)
                if existing is None:
                    collection.create_index(
                        request.configuration.scope_index_keys(),
                        name=request.configuration.scope_index_name,
                    )
                    created_count += 1
                elif request.configuration.matches_scope_index(existing):
                    unchanged_count += 1
                else:
                    raise MongoReadingEvidenceError(
                        code="index_conflict",
                        message="named MongoDB scope index differs",
                    )
        except MongoReadingEvidenceError:
            raise
        except PyMongoError as error:
            raise MongoReadingEvidenceError(
                code="index_failed",
                message="MongoDB reading-evidence index readiness failed",
            ) from error
        return MongoReadingEvidenceIndexReadinessResult(
            request=request,
            created_count=created_count,
            unchanged_count=unchanged_count,
        )

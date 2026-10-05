from __future__ import annotations

from typing import Any, cast

import mongomock
import pytest
from projectkoios.ingestion.integrations.mongodb.extraction.index_readiness import (  # noqa: E501
    MongoExtractionProjectionIndexReadinessBackend,
)
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.backend_error import (  # noqa: E501
    ExtractionProjectionIndexReadinessBackendError,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.configuration import (  # noqa: E501
    ExtractionProjectionIndexReadinessConfiguration,
)
from pymongo.database import Database


def _target(database_name: str) -> ExtractionProjectionTargetIdentity:
    return ExtractionProjectionTargetIdentity.create(
        deployment_id="local-test-mongodb",
        environment="test",
        database_name=database_name,
        schema_id="extraction-read-model-v1",
        projection_slot="extraction-publications",
    )


def test__mongodb_index_readiness__rejects_database_target_difference() -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_test)

    with pytest.raises(ValueError, match="database and index-readiness target"):
        MongoExtractionProjectionIndexReadinessBackend(
            database=database,
            configured_target=_target("different_database"),
            configured_configuration=(
                ExtractionProjectionIndexReadinessConfiguration.mongodb_v1()
            ),
        )


def test__mongodb_index_readiness__reports_conflicting_definition() -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_test)
    target = _target(database.name)
    configuration = ExtractionProjectionIndexReadinessConfiguration.mongodb_v1()
    backend = MongoExtractionProjectionIndexReadinessBackend(
        database=database,
        configured_target=target,
        configured_configuration=configuration,
    )
    definition = configuration.indexes[0]
    database[definition.collection_name].create_index(
        [("different_field", 1)],
        name=definition.index_name,
        unique=definition.unique,
    )

    with pytest.raises(
        ExtractionProjectionIndexReadinessBackendError
    ) as failure:
        backend.ensure_index_readiness(
            target=target,
            configuration=configuration,
            authority_id="authority:index-write",
        )

    assert failure.value.code == "projection_index_definition_differs"
    assert failure.value.disposition is (
        ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
    )

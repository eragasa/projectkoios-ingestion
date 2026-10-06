from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import mongomock
import pytest
from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.integrations.disk.extraction.store import (
    DiskExtractionPublicationStore,
)
from projectkoios.ingestion.integrations.mongodb.extraction.store import (
    MongoExtractionPublicationStore,
)
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.actions.status import (
    ExtractionActionStatus,
)
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.index.readiness.actionizer import (  # noqa: E501
    ExtractionProjectionIndexReadinessActionizer,
)
from projectkoios.ingestion.storage.extraction.projection.index.readiness.configuration import (  # noqa: E501
    ExtractionProjectionIndexReadinessConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.index.readiness.definition import (  # noqa: E501
    ExtractionProjectionIndexDefinition,
)
from projectkoios.ingestion.storage.extraction.projection.index.readiness.request import (  # noqa: E501
    ExtractionProjectionIndexReadinessRequest,
)
from pymongo.database import Database


def _target(
    database_name: str, *, slot: str = "extraction-publications"
) -> ExtractionProjectionTargetIdentity:
    return ExtractionProjectionTargetIdentity.create(
        deployment_id="local-test-mongodb",
        environment="test",
        database_name=database_name,
        schema_id="extraction-read-model-v1",
        projection_slot=slot,
    )


def _store(
    *, database: Database[dict[str, Any]], journal_root: Path
) -> MongoExtractionPublicationStore:
    return MongoExtractionPublicationStore(
        database=database,
        journal=DiskExtractionPublicationStore(journal_root),
        projection_target=_target(database.name),
        default_write_authority_id="authority:test-extraction-write",
    )


def test__index_readiness__is_a_configurable_actionizer(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_test)
    store = _store(database=database, journal_root=tmp_path / "journal")

    actionizer = ExtractionProjectionIndexReadinessActionizer(
        backend=store.index_readiness_backend
    )

    assert isinstance(actionizer, ConfigurableDataObjectActionizer)


def test__index_readiness__rejects_unbounded_index_keys() -> None:
    with pytest.raises(ValueError, match="index keys are invalid"):
        ExtractionProjectionIndexDefinition.create(
            collection_name="collection",
            index_name="too_many_keys",
            keys=tuple((f"field_{index}", 1) for index in range(17)),
            unique=False,
        )


def test__index_readiness__creates_and_observes_exact_indexes(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_test)
    store = _store(database=database, journal_root=tmp_path / "journal")
    configuration = ExtractionProjectionIndexReadinessConfiguration.mongodb_v1()
    request = ExtractionProjectionIndexReadinessRequest.create(
        target=store.projection_target,
        configuration=configuration,
        authority_id="authority:index-write",
    )

    result = ExtractionProjectionIndexReadinessActionizer(
        backend=store.index_readiness_backend
    ).action(request=request)

    assert result.status is ExtractionActionStatus.COMPLETED
    assert result.disposition is ExtractionActionDisposition.CONTINUE
    assert result.evidence is not None
    assert result.evidence.target_id == store.projection_target.target_id
    assert result.evidence.configuration_id == configuration.configuration_id
    assert result.evidence.authority_id == "authority:index-write"
    assert tuple(
        (item.collection_name, item.index_name, item.keys, item.unique)
        for item in result.evidence.indexes
    ) == tuple(
        (
            definition.collection_name,
            definition.index_name,
            definition.keys,
            definition.unique,
        )
        for definition in configuration.indexes
    )


def test__index_readiness__replay_is_stable(tmp_path: Path) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_test)
    store = _store(database=database, journal_root=tmp_path / "journal")
    request = ExtractionProjectionIndexReadinessRequest.create(
        target=store.projection_target,
        configuration=(
            ExtractionProjectionIndexReadinessConfiguration.mongodb_v1()
        ),
        authority_id="authority:index-write",
    )
    actionizer = ExtractionProjectionIndexReadinessActionizer(
        backend=store.index_readiness_backend
    )

    first = actionizer.action(request=request)
    replay = actionizer.action(request=request)

    assert replay == first


def test__index_readiness__request_authority_does_not_change_idempotency(
    tmp_path: Path,
) -> None:
    configuration = ExtractionProjectionIndexReadinessConfiguration.mongodb_v1()
    target = _target("projectkoios_test")

    first = ExtractionProjectionIndexReadinessRequest.create(
        target=target,
        configuration=configuration,
        authority_id="authority:first",
    )
    second = ExtractionProjectionIndexReadinessRequest.create(
        target=target,
        configuration=configuration,
        authority_id="authority:second",
    )

    assert first.request_id != second.request_id
    assert first.idempotency_key == second.idempotency_key


def test__index_readiness__rejects_conflicting_observed_definition(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_test)
    store = _store(database=database, journal_root=tmp_path / "journal")
    configuration = ExtractionProjectionIndexReadinessConfiguration.mongodb_v1()
    definition = configuration.indexes[0]
    database[definition.collection_name].create_index(
        [("different_field", 1)],
        name=definition.index_name,
        unique=definition.unique,
    )
    request = ExtractionProjectionIndexReadinessRequest.create(
        target=store.projection_target,
        configuration=configuration,
        authority_id="authority:index-write",
    )

    result = ExtractionProjectionIndexReadinessActionizer(
        backend=store.index_readiness_backend
    ).action(request=request)

    assert result.status is ExtractionActionStatus.FAILED
    assert result.disposition is (
        ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
    )
    assert result.failure_code == "projection_index_definition_differs"
    assert result.evidence is None


def test__index_readiness__rejects_different_configured_target(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_test)
    store = _store(database=database, journal_root=tmp_path / "journal")
    request = ExtractionProjectionIndexReadinessRequest.create(
        target=_target(database.name, slot="other-slot"),
        configuration=(
            ExtractionProjectionIndexReadinessConfiguration.mongodb_v1()
        ),
        authority_id="authority:index-write",
    )

    result = ExtractionProjectionIndexReadinessActionizer(
        backend=store.index_readiness_backend
    ).action(request=request)

    assert result.status is ExtractionActionStatus.FAILED
    assert result.disposition is (
        ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
    )
    assert result.failure_code == "projection_target_differs"
    assert result.evidence is None

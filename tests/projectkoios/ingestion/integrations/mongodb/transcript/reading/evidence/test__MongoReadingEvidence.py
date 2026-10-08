"""MongoDB reading-evidence adapter tests against in-memory capabilities."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

import mongomock
import pytest
from projectkoios.ingestion.base.materializer.request import (
    MaterializationRequest,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.configuration import (  # noqa: E501
    MongoReadingEvidenceConfiguration,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.error import (  # noqa: E501
    MongoReadingEvidenceError,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.index.readiness.actionizer import (  # noqa: E501
    MongoReadingEvidenceIndexReadinessActionizer,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.index.readiness.request import (  # noqa: E501
    MongoReadingEvidenceIndexReadinessRequest,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.index.readiness.result import (  # noqa: E501
    MongoReadingEvidenceIndexReadinessResult,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.materialization.actionizer import (  # noqa: E501
    MongoReadingEvidenceMaterializer,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.source.actionizer import (  # noqa: E501
    MongoReadingEvidenceSourceActionizer,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.source.reader import (  # noqa: E501
    MongoReadingEvidenceReadModelReader,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.configuration import (  # noqa: E501
    ReadingEvidenceMaterializationConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.target import (  # noqa: E501
    ReadingEvidenceMaterializationTarget,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.collection import (  # noqa: E501
    ReadingEvidenceStorageCollection,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.schema.version import (  # noqa: E501
    ReadingEvidenceStorageSchemaVersion,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.source.verifier import (  # noqa: E501
    ReadingEvidenceReadModelVerifier,
)
from pymongo.database import Database
from pymongo.errors import PyMongoError

from tests.projectkoios.ingestion.storage.transcript.reading.evidence.fixture import (  # noqa: E501
    ReadingEvidenceStorageFixture,
)

MongoDocument = dict[str, Any]


class _RecordingCollection:
    def __init__(self, *, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events
        self.documents: dict[str, MongoDocument] = {}

    def find_one(self, query: MongoDocument) -> MongoDocument | None:
        value = self.documents.get(cast(str, query["_id"]))
        return None if value is None else deepcopy(value)

    def create_index(
        self,
        keys: object,
        *,
        name: str,
    ) -> str:
        del keys
        return name

    def insert_one(self, value: MongoDocument) -> None:
        self.events.append(self.name)
        self.documents[cast(str, value["_id"])] = deepcopy(value)


class _RecordingDatabase:
    def __init__(self, *, name: str) -> None:
        self.name = name
        self.events: list[str] = []
        self.collections: dict[str, _RecordingCollection] = {}

    def __getitem__(self, name: str) -> _RecordingCollection:
        return self.collections.setdefault(
            name,
            _RecordingCollection(name=name, events=self.events),
        )


def _target(
    configuration: MongoReadingEvidenceConfiguration,
    *,
    store_name: str,
) -> ReadingEvidenceMaterializationTarget:
    return ReadingEvidenceMaterializationTarget.create(
        deployment_id="unit-test",
        environment="test",
        store_name=store_name,
        schema_id=configuration.materialization.schema_id,
    )


def _ensure_indexes(
    *,
    database: Database[MongoDocument],
    target: ReadingEvidenceMaterializationTarget,
    configuration: MongoReadingEvidenceConfiguration,
) -> MongoReadingEvidenceIndexReadinessResult:
    actionizer = MongoReadingEvidenceIndexReadinessActionizer(
        database=database,
        configured_target=target,
    )
    request = MongoReadingEvidenceIndexReadinessRequest(
        target=target,
        configuration=configuration,
        authority_id="unit-test-index-authority",
    )
    return actionizer.action(request=request)


def _raise_mongo_error(*args: object, **kwargs: object) -> None:
    del args, kwargs
    raise PyMongoError("expected provider failure")


def _bounded_configuration(
    *, maximum_document_bytes: int
) -> MongoReadingEvidenceConfiguration:
    default = MongoReadingEvidenceConfiguration.v1()
    names = default.materialization.names()
    return MongoReadingEvidenceConfiguration(
        materialization=ReadingEvidenceMaterializationConfiguration.create(
            schema_version=ReadingEvidenceStorageSchemaVersion.current(),
            documents_name=names[ReadingEvidenceStorageCollection.DOCUMENTS],
            pages_name=names[ReadingEvidenceStorageCollection.PAGES],
            blocks_name=names[ReadingEvidenceStorageCollection.BLOCKS],
            producers_name=names[ReadingEvidenceStorageCollection.PRODUCERS],
            references_name=names[ReadingEvidenceStorageCollection.REFERENCES],
            limitations_name=names[
                ReadingEvidenceStorageCollection.LIMITATIONS
            ],
            completions_name=names[
                ReadingEvidenceStorageCollection.COMPLETIONS
            ],
            maximum_document_bytes=maximum_document_bytes,
        ),
        cursor_batch_size=default.cursor_batch_size,
        scope_index_name=default.scope_index_name,
    )


def _materialization_request(
    fixture: ReadingEvidenceStorageFixture,
    configuration: MongoReadingEvidenceConfiguration,
    target: ReadingEvidenceMaterializationTarget,
) -> MaterializationRequest[Any, Any, Any]:
    return MaterializationRequest.create(
        projection=fixture.read_model,
        target=target,
        configuration=configuration.materialization,
        authority_id="unit-test-write-authority",
    )


def test__index_readiness__rejects_conflicting_named_definition() -> None:
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    collection_name = next(iter(configuration.materialization.names().values()))
    database[collection_name].create_index(
        (("wrong_scope", 1),),
        name=configuration.scope_index_name,
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        _ensure_indexes(
            database=database,
            target=target,
            configuration=configuration,
        )

    assert raised.value.code == "index_conflict"


def test__index_readiness__rejects_same_key_partial_index() -> None:
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    collection_name = next(iter(configuration.materialization.names().values()))
    database[collection_name].create_index(
        configuration.scope_index_keys(),
        name=configuration.scope_index_name,
        partialFilterExpression={"record_kind": "completion"},
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        _ensure_indexes(
            database=database,
            target=target,
            configuration=configuration,
        )

    assert raised.value.code == "index_conflict"


def test__materializer__writes_completion_last_and_replays_exactly() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = MongoReadingEvidenceConfiguration.v1()
    database = _RecordingDatabase(name="reading_evidence_test")
    target = _target(configuration, store_name=database.name)
    materializer = MongoReadingEvidenceMaterializer(
        database=cast(Database[MongoDocument], database),
        configured_target=target,
        configuration=configuration,
    )
    request = _materialization_request(fixture, configuration, target)

    first = materializer.action(request=request)
    first_events = tuple(database.events)
    second = materializer.action(request=request)

    names = configuration.materialization.names()
    assert (
        first_events[-1] == names[ReadingEvidenceStorageCollection.COMPLETIONS]
    )
    assert len(database.events) == len(first_events)
    assert sum(
        value.created_count for value in first.evidence.collections
    ) == len(fixture.read_model.documents)
    assert sum(
        value.unchanged_count for value in second.evidence.collections
    ) == len(fixture.read_model.documents)


def test__mongo_source__returns_exact_canonical_document() -> None:
    fixture = ReadingEvidenceStorageFixture.visual()
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    first_indexes = _ensure_indexes(
        database=database,
        target=target,
        configuration=configuration,
    )
    second_indexes = _ensure_indexes(
        database=database,
        target=target,
        configuration=configuration,
    )
    assert first_indexes.created_count == len(
        configuration.materialization.names()
    )
    assert second_indexes.unchanged_count == len(
        configuration.materialization.names()
    )
    materializer = MongoReadingEvidenceMaterializer(
        database=database,
        configured_target=target,
        configuration=configuration,
    )
    materializer.action(
        request=_materialization_request(fixture, configuration, target)
    )
    for collection_name in configuration.materialization.names().values():
        index = database[collection_name].index_information()[
            configuration.scope_index_name
        ]
        assert tuple(index["key"]) == (
            ("schema_id", 1),
            ("generation_id", 1),
            ("evidence_document_id", 1),
            ("_id", 1),
        )
    reader = MongoReadingEvidenceReadModelReader(
        database=database,
        configured_target=target,
        configuration=configuration,
        generation_id=fixture.generation_id,
    )

    result = MongoReadingEvidenceSourceActionizer(
        reader=reader,
        verifier=ReadingEvidenceReadModelVerifier(),
    ).action(
        request=fixture.source_request(provider_source_id=reader.source_id)
    )

    assert result.document == fixture.canonical.document
    assert result.inventory == fixture.canonical.inventory


def test__mongo_source__rejects_missing_scope_indexes() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    MongoReadingEvidenceMaterializer(
        database=database,
        configured_target=target,
        configuration=configuration,
    ).action(request=_materialization_request(fixture, configuration, target))
    reader = MongoReadingEvidenceReadModelReader(
        database=database,
        configured_target=target,
        configuration=configuration,
        generation_id=fixture.generation_id,
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        reader.read(
            request=fixture.source_request(provider_source_id=reader.source_id)
        )

    assert raised.value.code == "index_not_ready"


def test__mongo_source__rejects_same_key_partial_index() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    _ensure_indexes(
        database=database,
        target=target,
        configuration=configuration,
    )
    names = configuration.materialization.names()
    collection = database[names[ReadingEvidenceStorageCollection.DOCUMENTS]]
    collection.drop_index(configuration.scope_index_name)
    collection.create_index(
        configuration.scope_index_keys(),
        name=configuration.scope_index_name,
        partialFilterExpression={"record_kind": "document"},
    )
    reader = MongoReadingEvidenceReadModelReader(
        database=database,
        configured_target=target,
        configuration=configuration,
        generation_id=fixture.generation_id,
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        reader.read(
            request=fixture.source_request(provider_source_id=reader.source_id)
        )

    assert raised.value.code == "index_not_ready"


def test__mongo_source__rejects_partial_generation_without_completion() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    _ensure_indexes(
        database=database,
        target=target,
        configuration=configuration,
    )
    MongoReadingEvidenceMaterializer(
        database=database,
        configured_target=target,
        configuration=configuration,
    ).action(request=_materialization_request(fixture, configuration, target))
    names = configuration.materialization.names()
    database[names[ReadingEvidenceStorageCollection.COMPLETIONS]].delete_many(
        {}
    )
    reader = MongoReadingEvidenceReadModelReader(
        database=database,
        configured_target=target,
        configuration=configuration,
        generation_id=fixture.generation_id,
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        reader.read(
            request=fixture.source_request(provider_source_id=reader.source_id)
        )

    assert raised.value.code == "completion_missing"


def test__mongo_source__rejects_missing_manifested_child_record() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    _ensure_indexes(
        database=database,
        target=target,
        configuration=configuration,
    )
    MongoReadingEvidenceMaterializer(
        database=database,
        configured_target=target,
        configuration=configuration,
    ).action(request=_materialization_request(fixture, configuration, target))
    names = configuration.materialization.names()
    producer_collection = database[
        names[ReadingEvidenceStorageCollection.PRODUCERS]
    ]
    producer = producer_collection.find_one({})
    assert producer is not None
    producer_collection.delete_one({"_id": producer["_id"]})
    reader = MongoReadingEvidenceReadModelReader(
        database=database,
        configured_target=target,
        configuration=configuration,
        generation_id=fixture.generation_id,
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        reader.read(
            request=fixture.source_request(provider_source_id=reader.source_id)
        )

    assert raised.value.code == "collection_count_mismatch"


def test__mongo_source__rejects_unmanifested_extra_record() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    _ensure_indexes(
        database=database,
        target=target,
        configuration=configuration,
    )
    MongoReadingEvidenceMaterializer(
        database=database,
        configured_target=target,
        configuration=configuration,
    ).action(request=_materialization_request(fixture, configuration, target))
    names = configuration.materialization.names()
    collection = database[names[ReadingEvidenceStorageCollection.PRODUCERS]]
    extra = collection.find_one({})
    assert extra is not None
    extra["_id"] += ":extra"
    collection.insert_one(extra)
    reader = MongoReadingEvidenceReadModelReader(
        database=database,
        configured_target=target,
        configuration=configuration,
        generation_id=fixture.generation_id,
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        reader.read(
            request=fixture.source_request(provider_source_id=reader.source_id)
        )

    assert raised.value.code == "collection_extra_records"


def test__mongo_source__rejects_extra_record_in_completion_collection() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    _ensure_indexes(
        database=database,
        target=target,
        configuration=configuration,
    )
    MongoReadingEvidenceMaterializer(
        database=database,
        configured_target=target,
        configuration=configuration,
    ).action(request=_materialization_request(fixture, configuration, target))
    names = configuration.materialization.names()
    producer = database[
        names[ReadingEvidenceStorageCollection.PRODUCERS]
    ].find_one({})
    assert producer is not None
    database[names[ReadingEvidenceStorageCollection.COMPLETIONS]].insert_one(
        producer
    )
    reader = MongoReadingEvidenceReadModelReader(
        database=database,
        configured_target=target,
        configuration=configuration,
        generation_id=fixture.generation_id,
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        reader.read(
            request=fixture.source_request(provider_source_id=reader.source_id)
        )

    assert raised.value.code == "collection_extra_records"


def test__mongo_source__rejects_duplicate_completion_member() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    _ensure_indexes(
        database=database,
        target=target,
        configuration=configuration,
    )
    MongoReadingEvidenceMaterializer(
        database=database,
        configured_target=target,
        configuration=configuration,
    ).action(request=_materialization_request(fixture, configuration, target))
    names = configuration.materialization.names()
    completions = database[names[ReadingEvidenceStorageCollection.COMPLETIONS]]
    duplicate = completions.find_one({})
    assert duplicate is not None
    duplicate["_id"] += ":duplicate"
    completions.insert_one(duplicate)
    reader = MongoReadingEvidenceReadModelReader(
        database=database,
        configured_target=target,
        configuration=configuration,
        generation_id=fixture.generation_id,
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        reader.read(
            request=fixture.source_request(provider_source_id=reader.source_id)
        )

    assert raised.value.code == "collection_extra_records"


def test__mongo_source__rejects_wrong_role_only_completion_member() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    _ensure_indexes(
        database=database,
        target=target,
        configuration=configuration,
    )
    MongoReadingEvidenceMaterializer(
        database=database,
        configured_target=target,
        configuration=configuration,
    ).action(request=_materialization_request(fixture, configuration, target))
    names = configuration.materialization.names()
    producer = database[
        names[ReadingEvidenceStorageCollection.PRODUCERS]
    ].find_one({})
    assert producer is not None
    completions = database[names[ReadingEvidenceStorageCollection.COMPLETIONS]]
    completions.delete_many({})
    completions.insert_one(producer)
    reader = MongoReadingEvidenceReadModelReader(
        database=database,
        configured_target=target,
        configuration=configuration,
        generation_id=fixture.generation_id,
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        reader.read(
            request=fixture.source_request(provider_source_id=reader.source_id)
        )

    assert raised.value.code == "collection_role_mismatch"


def test__materializer__rejects_same_identity_with_changed_content() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    materializer = MongoReadingEvidenceMaterializer(
        database=database,
        configured_target=target,
        configuration=configuration,
    )
    request = _materialization_request(fixture, configuration, target)
    materializer.action(request=request)
    names = configuration.materialization.names()
    collection = database[names[ReadingEvidenceStorageCollection.DOCUMENTS]]
    existing = collection.find_one({})
    assert existing is not None
    existing["semantic_id"] += ":changed"
    collection.replace_one({"_id": existing["_id"]}, existing)

    with pytest.raises(MongoReadingEvidenceError) as raised:
        materializer.action(request=request)

    assert raised.value.code == "identity_conflict"


def test__materializer__rejects_member_over_bson_byte_bound() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = _bounded_configuration(maximum_document_bytes=1)
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    materializer = MongoReadingEvidenceMaterializer(
        database=database,
        configured_target=target,
        configuration=configuration,
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        materializer.action(
            request=_materialization_request(
                fixture,
                configuration,
                target,
            )
        )

    assert raised.value.code == "bson_byte_limit"


def test__index_readiness__translates_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    first_name = next(iter(configuration.materialization.names().values()))
    monkeypatch.setattr(
        database[first_name],
        "index_information",
        _raise_mongo_error,
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        _ensure_indexes(
            database=database,
            target=target,
            configuration=configuration,
        )

    assert raised.value.code == "index_failed"


def test__materializer__translates_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    names = configuration.materialization.names()
    monkeypatch.setattr(
        database[names[ReadingEvidenceStorageCollection.PRODUCERS]],
        "find_one",
        _raise_mongo_error,
    )
    materializer = MongoReadingEvidenceMaterializer(
        database=database,
        configured_target=target,
        configuration=configuration,
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        materializer.action(
            request=_materialization_request(
                fixture,
                configuration,
                target,
            )
        )

    assert raised.value.code == "write_failed"


def test__mongo_source__translates_provider_read_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = MongoReadingEvidenceConfiguration.v1()
    client = mongomock.MongoClient()
    database = client["reading_evidence_test"]
    target = _target(configuration, store_name=database.name)
    _ensure_indexes(
        database=database,
        target=target,
        configuration=configuration,
    )
    MongoReadingEvidenceMaterializer(
        database=database,
        configured_target=target,
        configuration=configuration,
    ).action(request=_materialization_request(fixture, configuration, target))
    names = configuration.materialization.names()
    monkeypatch.setattr(
        database[names[ReadingEvidenceStorageCollection.COMPLETIONS]],
        "find",
        _raise_mongo_error,
    )
    reader = MongoReadingEvidenceReadModelReader(
        database=database,
        configured_target=target,
        configuration=configuration,
        generation_id=fixture.generation_id,
    )

    with pytest.raises(MongoReadingEvidenceError) as raised:
        reader.read(
            request=fixture.source_request(provider_source_id=reader.source_id)
        )

    assert raised.value.code == "read_failed"

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import mongomock
import pytest
from projectkoios.ingestion.base.materializer.identity.error import (
    MaterializationIdentityError,
)
from projectkoios.ingestion.base.materializer.request import (
    MaterializationRequest,
)
from projectkoios.ingestion.base.materializer.result import (
    MaterializationResult,
)
from projectkoios.ingestion.base.projector.request import ProjectionRequest
from projectkoios.ingestion.integrations.disk.extraction.store import (
    DiskExtractionPublicationStore,
)
from projectkoios.ingestion.integrations.mongodb.extraction.materialization.error import (  # noqa: E501
    MongoExtractionProjectionMaterializationError,
)
from projectkoios.ingestion.integrations.mongodb.extraction.materializer import (  # noqa: E501
    MongoExtractionProjectionMaterializer,
)
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionResult,
    IngestionManifest,
    IngestionStatus,
    SourceDocument,
    SourceSpan,
)
from projectkoios.ingestion.storage.extraction.materialization.configuration import (  # noqa: E501
    ExtractionProjectionMaterializationConfiguration,
)
from projectkoios.ingestion.storage.extraction.materialization.evidence.model import (  # noqa: E501
    ExtractionProjectionMaterializationEvidence,
)
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.configuration import (
    ExtractionProjectionConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.evidence import (
    ExtractionPublicationEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.projector import (
    ExtractionProjectionProjector,
)
from projectkoios.ingestion.storage.extraction.projection.read.model import (
    ExtractionReadModel,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)
from pymongo.database import Database


@pytest.fixture
def extraction_result() -> ExtractionResult:
    source = SourceDocument.from_bytes(
        b"%PDF materializer fixture",
        source_id="source:materializer-fixture",
        media_type="application/pdf",
        locator="materializer-fixture.pdf",
    )
    block = ExtractedBlock.create(
        kind="paragraph",
        source_spans=(
            SourceSpan(
                source_id=source.source_id,
                source_blob_id=source.blob_id,
                page_index=0,
                bounding_box=(1.0, 2.0, 10.0, 12.0),
            ),
        ),
        extraction_method="fixture",
        confidence=1.0,
        text="Exact bounded text.",
    )
    document = ExtractedDocument.create(
        source=source,
        pages=(
            ExtractedPage(
                page_index=0,
                width=100.0,
                height=200.0,
                blocks=(block,),
            ),
        ),
    )
    manifest = IngestionManifest.create(
        source=source,
        extractor_name="fixture-extractor",
        extractor_version="1",
        configuration_digest="configuration:materializer-fixture",
        object_ids=(document.document_id, block.block_id),
        warning_ids=(),
        status=IngestionStatus.COMPLETED,
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
    )
    return ExtractionResult(document=document, manifest=manifest)


def _read_model(
    *,
    extraction: ExtractionResult,
    tmp_path: Path,
) -> ExtractionReadModel:
    journal = DiskExtractionPublicationStore(tmp_path / "journal")
    journal.publish(
        request=ExtractionPublicationRequest.create(extraction=extraction)
    )
    record = journal.records()[0]
    evidence = ExtractionPublicationEvidence.create(
        record=record,
        payload=journal.payload(record),
    )
    request = ProjectionRequest.create(
        sources=(evidence,),
        configuration=ExtractionProjectionConfiguration.v1(),
    )
    return ExtractionProjectionProjector().action(request=request).projection


def _target(
    database: Database[dict[str, Any]],
) -> ExtractionProjectionTargetIdentity:
    return ExtractionProjectionTargetIdentity.create(
        deployment_id="local-test-mongodb",
        environment="test",
        database_name=database.name,
        schema_id="extraction-read-model-v1",
        projection_slot="extraction-publications",
    )


def _materialize(
    *,
    materializer: MongoExtractionProjectionMaterializer,
    read_model: ExtractionReadModel,
    target: ExtractionProjectionTargetIdentity,
) -> MaterializationResult[ExtractionProjectionMaterializationEvidence]:
    request = MaterializationRequest.create(
        projection=read_model,
        target=target,
        configuration=ExtractionProjectionMaterializationConfiguration.mongodb_v1(),
        authority_id="authority:test-extraction-write",
    )
    return materializer.action(request=request)


def test__mongo_materializer__creates_then_replays_exact_read_model(
    extraction_result: ExtractionResult,
    tmp_path: Path,
) -> None:
    database = cast(
        Database[dict[str, Any]],
        mongomock.MongoClient().projectkoios_materializer,
    )
    target = _target(database)
    materializer = MongoExtractionProjectionMaterializer(
        database=database,
        configured_target=target,
    )
    read_model = _read_model(
        extraction=extraction_result,
        tmp_path=tmp_path,
    )

    created = _materialize(
        materializer=materializer,
        read_model=read_model,
        target=target,
    ).evidence
    replayed = _materialize(
        materializer=materializer,
        read_model=read_model,
        target=target,
    ).evidence
    configuration = (
        ExtractionProjectionMaterializationConfiguration.mongodb_v1()
    )

    assert created.created_document_count == len(read_model.documents)
    assert replayed.unchanged_document_count == len(read_model.documents)
    assert database[configuration.documents_collection].count_documents({}) == 1
    assert database[configuration.blocks_collection].count_documents({}) == 1


def test__mongo_materializer__repairs_content_when_digest_marker_is_intact(
    extraction_result: ExtractionResult,
    tmp_path: Path,
) -> None:
    database = cast(
        Database[dict[str, Any]],
        mongomock.MongoClient().projectkoios_materializer,
    )
    target = _target(database)
    materializer = MongoExtractionProjectionMaterializer(
        database=database,
        configured_target=target,
    )
    read_model = _read_model(
        extraction=extraction_result,
        tmp_path=tmp_path,
    )
    _materialize(
        materializer=materializer,
        read_model=read_model,
        target=target,
    )
    configuration = (
        ExtractionProjectionMaterializationConfiguration.mongodb_v1()
    )
    collection = configuration.blocks_collection
    database[collection].update_one({}, {"$set": {"text": "tampered"}})

    _materialize(
        materializer=materializer,
        read_model=read_model,
        target=target,
    )

    assert database[collection].find_one()["text"] == "Exact bounded text."


def test__mongo_materializer__rejects_unsupported_projection_schema(
    extraction_result: ExtractionResult,
    tmp_path: Path,
) -> None:
    database = cast(
        Database[dict[str, Any]],
        mongomock.MongoClient().projectkoios_materializer,
    )
    target = _target(database)
    materializer = MongoExtractionProjectionMaterializer(
        database=database,
        configured_target=target,
    )
    read_model = _read_model(
        extraction=extraction_result,
        tmp_path=tmp_path,
    )
    unsupported = ExtractionReadModel.create(
        source_evidence_ids=read_model.source_evidence_ids,
        configuration_id=read_model.configuration_id,
        schema_id="unsupported-extraction-read-model",
        documents=read_model.documents,
    )

    with pytest.raises(
        MaterializationIdentityError,
        match="schema identities differ",
    ):
        _materialize(
            materializer=materializer,
            read_model=unsupported,
            target=target,
        )

    assert database.list_collection_names() == []


def test__mongo_materializer__rejects_changed_content_identity(
    extraction_result: ExtractionResult,
    tmp_path: Path,
) -> None:
    database = cast(
        Database[dict[str, Any]],
        mongomock.MongoClient().projectkoios_materializer,
    )
    target = _target(database)
    materializer = MongoExtractionProjectionMaterializer(
        database=database,
        configured_target=target,
    )
    read_model = _read_model(
        extraction=extraction_result,
        tmp_path=tmp_path,
    )
    _materialize(
        materializer=materializer,
        read_model=read_model,
        target=target,
    )
    configuration = (
        ExtractionProjectionMaterializationConfiguration.mongodb_v1()
    )
    collection = configuration.blocks_collection
    database[collection].update_one(
        {},
        {"$set": {"projection_content_sha256": "0" * 64}},
    )

    with pytest.raises(
        MongoExtractionProjectionMaterializationError,
        match="conflicting content",
    ) as caught:
        _materialize(
            materializer=materializer,
            read_model=read_model,
            target=target,
        )

    assert caught.value.code == "projection_identity_conflict"

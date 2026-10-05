from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import mongomock
import pytest
from projectkoios.ingestion.base.projector.request import ProjectionRequest
from projectkoios.ingestion.integrations.disk.extraction.store import (
    DiskExtractionPublicationStore,
)
from projectkoios.ingestion.integrations.mongodb.extraction.materialization_error import (  # noqa: E501
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
from projectkoios.ingestion.storage.extraction.projection.configuration import (
    ExtractionProjectionConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.evidence import (
    ExtractionPublicationEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.projector import (
    ExtractionProjectionProjector,
)
from projectkoios.ingestion.storage.extraction.projection.read_model import (
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


def test__mongo_materializer__creates_then_replays_exact_read_model(
    extraction_result: ExtractionResult,
    tmp_path: Path,
) -> None:
    database = cast(
        Database[dict[str, Any]],
        mongomock.MongoClient().projectkoios_materializer,
    )
    materializer = MongoExtractionProjectionMaterializer(database=database)
    read_model = _read_model(
        extraction=extraction_result,
        tmp_path=tmp_path,
    )

    created = materializer.materialize(read_model=read_model)
    replayed = materializer.materialize(read_model=read_model)

    assert created == 1
    assert replayed == 0
    assert database[materializer.DOCUMENTS].count_documents({}) == 1
    assert database[materializer.BLOCKS].count_documents({}) == 1


def test__mongo_materializer__repairs_content_when_digest_marker_is_intact(
    extraction_result: ExtractionResult,
    tmp_path: Path,
) -> None:
    database = cast(
        Database[dict[str, Any]],
        mongomock.MongoClient().projectkoios_materializer,
    )
    materializer = MongoExtractionProjectionMaterializer(database=database)
    read_model = _read_model(
        extraction=extraction_result,
        tmp_path=tmp_path,
    )
    materializer.materialize(read_model=read_model)
    database[materializer.BLOCKS].update_one({}, {"$set": {"text": "tampered"}})

    materializer.materialize(read_model=read_model)

    assert database[materializer.BLOCKS].find_one()["text"] == (
        "Exact bounded text."
    )


def test__mongo_materializer__rejects_unsupported_projection_schema(
    extraction_result: ExtractionResult,
    tmp_path: Path,
) -> None:
    database = cast(
        Database[dict[str, Any]],
        mongomock.MongoClient().projectkoios_materializer,
    )
    materializer = MongoExtractionProjectionMaterializer(database=database)
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
        MongoExtractionProjectionMaterializationError,
        match="does not support this schema",
    ) as caught:
        materializer.materialize(read_model=unsupported)

    assert caught.value.code == "projection_schema_unsupported"
    assert database.list_collection_names() == []


def test__mongo_materializer__rejects_changed_content_identity(
    extraction_result: ExtractionResult,
    tmp_path: Path,
) -> None:
    database = cast(
        Database[dict[str, Any]],
        mongomock.MongoClient().projectkoios_materializer,
    )
    materializer = MongoExtractionProjectionMaterializer(database=database)
    read_model = _read_model(
        extraction=extraction_result,
        tmp_path=tmp_path,
    )
    materializer.materialize(read_model=read_model)
    database[materializer.BLOCKS].update_one(
        {},
        {"$set": {"projection_content_sha256": "0" * 64}},
    )

    with pytest.raises(
        MongoExtractionProjectionMaterializationError,
        match="conflicting content",
    ) as caught:
        materializer.materialize(read_model=read_model)

    assert caught.value.code == "projection_identity_conflict"

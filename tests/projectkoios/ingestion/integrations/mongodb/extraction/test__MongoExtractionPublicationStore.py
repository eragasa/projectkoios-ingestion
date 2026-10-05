from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import mongomock
from projectkoios.ingestion.integrations.disk.extraction.store import (
    DiskExtractionPublicationStore,
)
from projectkoios.ingestion.integrations.mongodb.extraction.store import (
    MongoExtractionPublicationStore,
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
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.actions.status import (
    ExtractionActionStatus,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.actionizer import (  # noqa: E501
    ExtractionProjectionInventoryActionizer,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.request import (  # noqa: E501
    ExtractionProjectionInventoryRequest,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)
from projectkoios.ingestion.storage.extraction.recovery.request import (
    ExtractionProjectionRecoveryRequest,
)
from projectkoios.ingestion.storage.extraction.selected_recovery.actionizer import (  # noqa: E501
    SelectedExtractionProjectionRecoveryActionizer,
)
from projectkoios.ingestion.storage.extraction.selected_recovery.request import (  # noqa: E501
    SelectedExtractionProjectionRecoveryRequest,
)
from pymongo.database import Database


def _extraction(suffix: str = "fixture") -> ExtractionResult:
    source = SourceDocument.from_bytes(
        f"%PDF MongoDB projection {suffix}".encode(),
        source_id=f"source:mongodb-{suffix}",
        media_type="application/pdf",
        locator=f"mongodb-{suffix}.pdf",
    )
    block = ExtractedBlock.create(
        kind="paragraph",
        source_spans=(
            SourceSpan(
                source_id=source.source_id,
                source_blob_id=source.blob_id,
                page_index=0,
                bounding_box=(1.0, 2.0, 3.0, 4.0),
            ),
        ),
        extraction_method="fixture",
        confidence=1.0,
        text="Exact MongoDB text.",
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
        extractor_name="fixture",
        extractor_version="1",
        configuration_digest="configuration:mongodb-fixture",
        object_ids=(document.document_id, block.block_id),
        warning_ids=(),
        status=IngestionStatus.COMPLETED,
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
    )
    return ExtractionResult(document=document, manifest=manifest)


def test__mongo_extraction_publication_store__rebuilds_from_disk(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_test)
    journal = DiskExtractionPublicationStore(tmp_path / "journal")
    store = MongoExtractionPublicationStore(
        database=database,
        journal=journal,
    )
    extraction = _extraction()

    store.publish(
        request=ExtractionPublicationRequest.create(extraction=extraction)
    )

    assert database[store.DOCUMENTS].count_documents({}) == 1
    assert database[store.PAGES].count_documents({}) == 1
    assert database[store.BLOCKS].count_documents({}) == 1
    assert database[store.DOCUMENTS].find_one()["publication_state"] == (
        "complete"
    )

    for collection_name in database.list_collection_names():
        database[collection_name].delete_many({})
    recovered = store.recover(
        request=ExtractionProjectionRecoveryRequest.create()
    )

    assert recovered.projected_records == 1
    assert database[store.DOCUMENTS].count_documents({}) == 1
    assert database[store.BLOCKS].count_documents({}) == 1


def test__mongo_extraction_publication_store__inventories_owned_collections(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_inventory)
    journal = DiskExtractionPublicationStore(tmp_path / "journal")
    store = MongoExtractionPublicationStore(
        database=database,
        journal=journal,
        projection_reference="projection:development-fixture",
    )
    store.publish(
        request=ExtractionPublicationRequest.create(extraction=_extraction())
    )
    request = ExtractionProjectionInventoryRequest.create(
        projection_reference=store.projection_reference,
        authority_id="authority:development-query",
    )
    actionizer = ExtractionProjectionInventoryActionizer(reader=store)

    first = actionizer.action(request=request)
    second = actionizer.action(request=request)

    assert first == second
    assert first.status is ExtractionActionStatus.COMPLETED
    assert first.disposition is ExtractionActionDisposition.CONTINUE
    assert tuple(
        (item.collection_name, item.document_count)
        for item in first.collections
    ) == (
        (store.BLOCKS, 1),
        (store.DOCUMENTS, 1),
        (store.MANIFESTS, 1),
        (store.PAGES, 1),
        (store.WARNINGS, 0),
    )


def test__mongo_extraction_publication_store__rejects_other_projection(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_inventory)
    store = MongoExtractionPublicationStore(
        database=database,
        journal=DiskExtractionPublicationStore(tmp_path / "journal"),
        projection_reference="projection:development-fixture",
    )
    request = ExtractionProjectionInventoryRequest.create(
        projection_reference="projection:other",
        authority_id="authority:development-query",
    )

    result = ExtractionProjectionInventoryActionizer(reader=store).action(
        request=request
    )

    assert result.status is ExtractionActionStatus.FAILED
    assert (
        result.disposition
        is ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
    )
    assert result.failure_code == "projection_reference_differs"


def test__mongo_extraction_publication_store__recovers_exact_selection(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_recovery)
    journal = DiskExtractionPublicationStore(tmp_path / "journal")
    journal.publish(
        request=ExtractionPublicationRequest.create(
            extraction=_extraction("first")
        )
    )
    journal.publish(
        request=ExtractionPublicationRequest.create(
            extraction=_extraction("second")
        )
    )
    records = journal.records()
    store = MongoExtractionPublicationStore(
        database=database,
        journal=journal,
        projection_reference="projection:recovery-fixture",
    )
    request = SelectedExtractionProjectionRecoveryRequest.create(
        projection_reference=store.projection_reference,
        authority_id="authority:development-write",
        expected_journal_record_count=2,
        expected_journal_head_sha256=records[-1].record_sha256,
        selected_records=(records[1],),
        require_empty_projection=False,
    )
    actionizer = SelectedExtractionProjectionRecoveryActionizer(backend=store)

    created = actionizer.action(request=request)
    replayed = actionizer.action(request=request)

    assert created.status is ExtractionActionStatus.COMPLETED
    assert created.evidence is not None
    assert created.evidence.projected_record_count == 1
    assert created.evidence.last_selected_sequence == 2
    assert replayed.evidence is not None
    assert replayed.evidence.projected_record_count == 0
    assert replayed.evidence.unchanged_record_count == 1
    assert database[store.DOCUMENTS].count_documents({}) == 1


def test__mongo_extraction_publication_store__fails_on_journal_drift(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_recovery)
    journal = DiskExtractionPublicationStore(tmp_path / "journal")
    journal.publish(
        request=ExtractionPublicationRequest.create(extraction=_extraction())
    )
    records = journal.records()
    store = MongoExtractionPublicationStore(
        database=database,
        journal=journal,
        projection_reference="projection:recovery-fixture",
    )
    request = SelectedExtractionProjectionRecoveryRequest.create(
        projection_reference=store.projection_reference,
        authority_id="authority:development-write",
        expected_journal_record_count=1,
        expected_journal_head_sha256=records[-1].record_sha256,
        selected_records=records,
        require_empty_projection=True,
    )
    journal.publish(
        request=ExtractionPublicationRequest.create(
            extraction=_extraction("later")
        )
    )

    result = SelectedExtractionProjectionRecoveryActionizer(
        backend=store
    ).action(request=request)

    assert result.status is ExtractionActionStatus.FAILED
    assert (
        result.disposition
        is ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
    )
    assert result.failure_code == "authoritative_journal_identity_differs"


def test__mongo_extraction_publication_store__requires_empty_target(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_recovery)
    journal = DiskExtractionPublicationStore(tmp_path / "journal")
    publication = ExtractionPublicationRequest.create(extraction=_extraction())
    journal.publish(request=publication)
    records = journal.records()
    store = MongoExtractionPublicationStore(
        database=database,
        journal=journal,
        projection_reference="projection:recovery-fixture",
    )
    store.publish(request=publication)
    request = SelectedExtractionProjectionRecoveryRequest.create(
        projection_reference=store.projection_reference,
        authority_id="authority:development-write",
        expected_journal_record_count=1,
        expected_journal_head_sha256=records[-1].record_sha256,
        selected_records=records,
        require_empty_projection=True,
    )

    result = SelectedExtractionProjectionRecoveryActionizer(
        backend=store
    ).action(request=request)

    assert result.status is ExtractionActionStatus.FAILED
    assert result.failure_code == "projection_is_not_empty"

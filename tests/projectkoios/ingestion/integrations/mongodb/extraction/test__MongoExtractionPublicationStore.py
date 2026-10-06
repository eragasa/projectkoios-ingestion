from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import mongomock
from projectkoios.ingestion.base.inventory.request import InventoryRequest
from projectkoios.ingestion.base.projector.request import ProjectionRequest
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
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.configuration import (
    ExtractionProjectionConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.evidence import (
    ExtractionPublicationEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.actionizer import (  # noqa: E501
    ExtractionProjectionInventoryActionizer,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.configuration import (  # noqa: E501
    ExtractionProjectionInventoryConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.kind import (  # noqa: E501
    ExtractionProjectionEquivalenceKind,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.request import (  # noqa: E501
    ExtractionProjectionInventoryEquivalenceRequest,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.verifier import (  # noqa: E501
    ExtractionProjectionInventoryEquivalenceVerifier,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.expected import (  # noqa: E501
    ExpectedExtractionProjectionInventory,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.observer import (  # noqa: E501
    ExtractionProjectorInventory,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.request import (  # noqa: E501
    ExtractionProjectionInventoryRequest,
)
from projectkoios.ingestion.storage.extraction.projection.projector import (
    ExtractionProjectionProjector,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)
from projectkoios.ingestion.storage.extraction.recovery.request import (
    ExtractionProjectionRecoveryRequest,
)
from projectkoios.ingestion.storage.extraction.recovery.subset.actionizer import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryActionizer,
)
from projectkoios.ingestion.storage.extraction.recovery.subset.request import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryRequest,
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


def _store(
    *,
    database: Database[dict[str, Any]],
    journal: DiskExtractionPublicationStore,
) -> MongoExtractionPublicationStore:
    target = ExtractionProjectionTargetIdentity.create(
        deployment_id="local-test-mongodb",
        environment="test",
        database_name=database.name,
        schema_id="extraction-read-model-v1",
        projection_slot="extraction-publications",
    )
    return MongoExtractionPublicationStore(
        database=database,
        journal=journal,
        projection_target=target,
        default_write_authority_id="authority:test-extraction-write",
    )


def test__mongo_extraction_publication_store__rebuilds_from_disk(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_test)
    journal = DiskExtractionPublicationStore(tmp_path / "journal")
    store = _store(database=database, journal=journal)
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
    store = _store(database=database, journal=journal)
    store.publish(
        request=ExtractionPublicationRequest.create(extraction=_extraction())
    )
    request = ExtractionProjectionInventoryRequest.create(
        target=store.projection_target,
        configuration=ExtractionProjectionInventoryConfiguration.mongodb_v1(),
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


def test__mongo_inventory__matches_journal_derived_expected_content(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_inventory)
    journal = DiskExtractionPublicationStore(tmp_path / "journal")
    store = _store(database=database, journal=journal)
    store.publish(
        request=ExtractionPublicationRequest.create(extraction=_extraction())
    )
    record = journal.records()[0]
    source = ExtractionPublicationEvidence.create(
        record=record,
        payload=journal.payload(record),
    )
    projection = (
        ExtractionProjectionProjector()
        .action(
            request=ProjectionRequest.create(
                sources=(source,),
                configuration=ExtractionProjectionConfiguration.v1(),
            )
        )
        .projection
    )
    inventory_configuration = (
        ExtractionProjectionInventoryConfiguration.mongodb_v1()
    )
    expected = ExpectedExtractionProjectionInventory.from_read_models(
        read_models=(projection,),
        target=store.projection_target,
        configuration=inventory_configuration,
    )
    observed = (
        ExtractionProjectorInventory(reader=store)
        .action(
            request=InventoryRequest.create(
                target=store.projection_target,
                configuration=inventory_configuration,
                authority_id="authority:development-query",
            )
        )
        .evidence
    )
    comparison = ExtractionProjectionInventoryEquivalenceVerifier().action(
        request=ExtractionProjectionInventoryEquivalenceRequest.create(
            kind=ExtractionProjectionEquivalenceKind.INDEPENDENT_REBUILD,
            expected=expected,
            observed=observed,
        )
    )

    assert comparison.equivalent is True
    assert comparison.disposition is ExtractionActionDisposition.CONTINUE


def test__mongo_inventory__changes_after_any_stored_content_tamper(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_inventory)
    journal = DiskExtractionPublicationStore(tmp_path / "journal")
    store = _store(database=database, journal=journal)
    store.publish(
        request=ExtractionPublicationRequest.create(extraction=_extraction())
    )
    request = ExtractionProjectionInventoryRequest.create(
        target=store.projection_target,
        configuration=ExtractionProjectionInventoryConfiguration.mongodb_v1(),
        authority_id="authority:development-query",
    )
    actionizer = ExtractionProjectionInventoryActionizer(reader=store)
    before = actionizer.action(request=request)

    database[store.BLOCKS].update_one({}, {"$set": {"text": "tampered"}})
    after = actionizer.action(request=request)

    assert before.inventory_id != after.inventory_id
    before_block = next(
        item
        for item in before.collections
        if item.collection_name == store.BLOCKS
    )
    after_block = next(
        item
        for item in after.collections
        if item.collection_name == store.BLOCKS
    )
    assert before_block.content_sha256 != after_block.content_sha256


def test__mongo_extraction_publication_store__rejects_other_projection(
    tmp_path: Path,
) -> None:
    client = mongomock.MongoClient()
    database = cast(Database[dict[str, Any]], client.projectkoios_inventory)
    store = _store(
        database=database,
        journal=DiskExtractionPublicationStore(tmp_path / "journal"),
    )
    other_target = ExtractionProjectionTargetIdentity.create(
        deployment_id="other-test-mongodb",
        environment="test",
        database_name=database.name,
        schema_id="extraction-read-model-v1",
        projection_slot="extraction-publications",
    )
    request = ExtractionProjectionInventoryRequest.create(
        target=other_target,
        configuration=ExtractionProjectionInventoryConfiguration.mongodb_v1(),
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
    store = _store(database=database, journal=journal)
    request = ExtractionProjectionSubsetRecoveryRequest.create(
        projection_reference=store.projection_reference,
        authority_id="authority:development-write",
        expected_journal_record_count=2,
        expected_journal_head_sha256=records[-1].record_sha256,
        subset_records=(records[1],),
        require_empty_projection=False,
    )
    actionizer = ExtractionProjectionSubsetRecoveryActionizer(backend=store)

    created = actionizer.action(request=request)
    replayed = actionizer.action(request=request)

    assert created.status is ExtractionActionStatus.COMPLETED
    assert created.evidence is not None
    assert created.evidence.projected_record_count == 1
    assert created.evidence.last_subset_sequence == 2
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
    store = _store(database=database, journal=journal)
    request = ExtractionProjectionSubsetRecoveryRequest.create(
        projection_reference=store.projection_reference,
        authority_id="authority:development-write",
        expected_journal_record_count=1,
        expected_journal_head_sha256=records[-1].record_sha256,
        subset_records=records,
        require_empty_projection=True,
    )
    journal.publish(
        request=ExtractionPublicationRequest.create(
            extraction=_extraction("later")
        )
    )

    result = ExtractionProjectionSubsetRecoveryActionizer(backend=store).action(
        request=request
    )

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
    store = _store(database=database, journal=journal)
    store.publish(request=publication)
    request = ExtractionProjectionSubsetRecoveryRequest.create(
        projection_reference=store.projection_reference,
        authority_id="authority:development-write",
        expected_journal_record_count=1,
        expected_journal_head_sha256=records[-1].record_sha256,
        subset_records=records,
        require_empty_projection=True,
    )

    result = ExtractionProjectionSubsetRecoveryActionizer(backend=store).action(
        request=request
    )

    assert result.status is ExtractionActionStatus.FAILED
    assert result.failure_code == "projection_is_not_empty"

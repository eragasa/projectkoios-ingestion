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
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)
from projectkoios.ingestion.storage.extraction.recovery.request import (
    ExtractionProjectionRecoveryRequest,
)
from pymongo.database import Database


def _extraction() -> ExtractionResult:
    source = SourceDocument.from_bytes(
        b"%PDF MongoDB projection fixture",
        source_id="source:mongodb-fixture",
        media_type="application/pdf",
        locator="mongodb-fixture.pdf",
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

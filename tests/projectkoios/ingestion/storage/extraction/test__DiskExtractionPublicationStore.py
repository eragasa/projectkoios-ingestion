from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from projectkoios.ingestion.integrations.disk.extraction.store import (
    DiskExtractionPublicationStore,
)
from projectkoios.ingestion.models import (
    ExtractionResult,
    IngestionManifest,
)
from projectkoios.ingestion.storage.extraction.identity.conflict.error import (
    ExtractionPublicationIdentityConflictError,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)


def test__disk_extraction_publication_store__recovers_exact_payload(
    tmp_path: Path,
    extraction_result: ExtractionResult,
) -> None:
    store = DiskExtractionPublicationStore(tmp_path / "extraction-store")
    request = ExtractionPublicationRequest.create(
        extraction=extraction_result,
    )

    created = store.publish(request=request)
    replayed = store.publish(request=request)
    records = store.records()

    assert created.replayed is False
    assert replayed == replace(created, replayed=True)
    assert len(records) == 1
    assert store.payload(records[0]).decode("utf-8").startswith("{")


def test__disk_extraction_publication_store__repairs_torn_terminal_record(
    tmp_path: Path,
    extraction_result: ExtractionResult,
) -> None:
    store = DiskExtractionPublicationStore(tmp_path / "extraction-store")
    request = ExtractionPublicationRequest.create(
        extraction=extraction_result,
    )
    store.publish(request=request)
    with store.journal.open("ab") as stream:
        stream.write(b'{"sequence":2')
        stream.flush()

    replayed = store.publish(request=request)

    assert replayed.replayed is True
    assert len(store.records()) == 1
    assert store.journal.read_bytes().endswith(b"\n")


def test__disk_extraction_publication_store__allows_versioned_manifests(
    tmp_path: Path,
    extraction_result: ExtractionResult,
) -> None:
    store = DiskExtractionPublicationStore(tmp_path / "extraction-store")
    store.publish(
        request=ExtractionPublicationRequest.create(
            extraction=extraction_result,
        )
    )
    prior = extraction_result.manifest
    versioned = replace(
        extraction_result,
        manifest=IngestionManifest.create(
            source=extraction_result.document.source,
            extractor_name=prior.extractor_name,
            extractor_version=prior.extractor_version,
            configuration_digest="configuration:versioned",
            object_ids=prior.object_ids,
            warning_ids=prior.warning_ids,
            status=prior.status,
            started_at=prior.started_at,
            completed_at=prior.completed_at,
        ),
    )

    result = store.publish(
        request=ExtractionPublicationRequest.create(extraction=versioned)
    )

    assert result.journal_sequence == 2
    assert result.document_id == extraction_result.document.document_id


def test__disk_extraction_publication_store__rejects_conflicting_document(
    tmp_path: Path,
    extraction_result: ExtractionResult,
) -> None:
    store = DiskExtractionPublicationStore(tmp_path / "extraction-store")
    store.publish(
        request=ExtractionPublicationRequest.create(
            extraction=extraction_result,
        )
    )
    page = extraction_result.document.pages[0]
    block = replace(page.blocks[0], text="Different exact text.")
    conflicting = replace(
        extraction_result,
        document=replace(
            extraction_result.document,
            pages=(replace(page, blocks=(block,)),),
        ),
    )

    with pytest.raises(
        ExtractionPublicationIdentityConflictError,
        match="manifest was already published differently",
    ):
        store.publish(
            request=ExtractionPublicationRequest.create(
                extraction=conflicting,
            )
        )

from __future__ import annotations

import pytest
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


@pytest.fixture
def extraction_result() -> ExtractionResult:
    content = b"%PDF bounded extraction fixture"
    source = SourceDocument.from_bytes(
        content,
        source_id="source:storage-fixture",
        media_type="application/pdf",
        locator="private-fixture.pdf",
    )
    span = SourceSpan(
        source_id=source.source_id,
        source_blob_id=source.blob_id,
        page_index=0,
        bounding_box=(1.0, 2.0, 10.0, 12.0),
    )
    block = ExtractedBlock.create(
        kind="paragraph",
        source_spans=(span,),
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
                coordinate_system="pdf-points-top-left",
            ),
        ),
    )
    manifest = IngestionManifest.create(
        source=source,
        extractor_name="fixture-extractor",
        extractor_version="1",
        configuration_digest="configuration:fixture",
        object_ids=(document.document_id, block.block_id),
        warning_ids=(),
        status=IngestionStatus.COMPLETED,
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
    )
    return ExtractionResult(document=document, manifest=manifest)

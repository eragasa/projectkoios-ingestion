from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.base import (
    DataObjectActionizer,
    DataObjectActionRequest,
    DataObjectActionResult,
)
from projectkoios.ingestion.page.projection.actionizer import (
    PageProjectionActionizer,
)
from projectkoios.ingestion.page.projection.enrichment.actionizer import (
    PageProjectionEvidenceEnrichmentActionizer,
)
from projectkoios.ingestion.page.projection.enrichment.basis import (
    PageProjectionEvidenceRetainedTextBasis,
    PageProjectionEvidenceUnavailableReason,
    PageProjectionEvidenceWarningDetailStatus,
)
from projectkoios.ingestion.page.projection.enrichment.derivation import (
    derive_page_projection_text_warning_inventory,
)
from projectkoios.ingestion.page.projection.enrichment.inventory import (
    PageProjectionEvidenceEnrichmentInventory,
)
from projectkoios.ingestion.page.projection.enrichment.record import (
    PageProjectionEvidenceEnrichment,
    PageProjectionEvidenceUnavailable,
)
from projectkoios.ingestion.page.projection.enrichment.request import (
    PageProjectionEvidenceEnrichmentRequest,
)
from projectkoios.ingestion.page.projection.enrichment.result import (
    PageProjectionEvidenceEnrichmentResult,
)
from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.transcript.reading.evidence.block.text.evidence import (  # noqa: E501
    ReadingTextEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.source import (  # noqa: E501
    ReadingTextBlockSourceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.span.evidence import (
    ReadingSourceSpanEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.span.inventory import (
    ReadingSourceSpanEvidenceInventory,
)

from tests.projectkoios.ingestion.page.projection.test__CurrentPageProjection import (  # noqa: E501
    paragraph_canonical,
    projection_request,
    visual_canonical,
)


def enrich_paragraph() -> PageProjectionEvidenceEnrichmentResult:
    """Return one deterministic paragraph-only enrichment result."""
    projection = PageProjectionActionizer().action(
        request=projection_request(
            paragraph_canonical(),
            include_figure_captions=False,
        )
    )
    request = PageProjectionEvidenceEnrichmentRequest(projection=projection)
    return PageProjectionEvidenceEnrichmentActionizer().action(request=request)


def test__evidence_enrichment__is_pure_deterministic_action_contract() -> None:
    first = enrich_paragraph()
    request = first.request
    second = PageProjectionEvidenceEnrichmentActionizer().action(
        request=request
    )

    assert isinstance(request, DataObjectActionRequest)
    assert isinstance(
        PageProjectionEvidenceEnrichmentActionizer(),
        DataObjectActionizer,
    )
    assert isinstance(first, DataObjectActionResult)
    assert first == second
    assert first.page_projection_result_id == request.projection.result_id
    assert len(first.entries) == request.projection.pages.block_count == 1
    assert first.entries.available_count == 1
    assert first.entries.unavailable_count == 0


def test__evidence_enrichment__retains_exact_text_span_and_producer() -> None:
    result = enrich_paragraph()
    entry = next(iter(result.entries))
    projection = result.request.projection
    source_page = next(iter(projection.request.source_result.document.pages))
    source_block = next(iter(source_page.blocks))
    projected_page = next(iter(projection.pages))
    projected_block = next(iter(projected_page.blocks))

    assert type(source_block) is ReadingTextEvidenceBlock
    assert type(entry) is PageProjectionEvidenceEnrichment
    assert entry.source_evidence_id == projected_block.source_id.value
    assert entry.page_projection_block_id == projected_block.block_id
    assert entry.binding.source_id == projection.source_id.value
    assert entry.binding.document_id == projection.document_id.value
    assert entry.binding.source_page_id == source_page.page_id.value
    assert entry.binding.page_projection_page_id == projected_page.page_id
    assert entry.retained_text == "\n".join(
        value.raw_text for value in source_block.sources
    )
    assert entry.retained_text_basis is (
        PageProjectionEvidenceRetainedTextBasis.TEXT_BLOCK_RAW_SOURCE_SEQUENCE
    )
    assert tuple(entry.source_span_ids) == tuple(
        span.span_id.value
        for source in source_block.sources
        for span in source.source_spans
    )
    assert tuple(
        (
            value.source_record_id,
            value.source_block_id,
            value.producer_id,
            value.producer_version,
        )
        for value in entry.producers
    ) == tuple(
        (
            source.record_id.value,
            source.source_block_id.value,
            source.producer_id.value,
            source.producer_version,
        )
        for source in source_block.sources
    )
    assert not entry.warnings
    assert not entry.limitations


def test__evidence_enrichment__caption_is_explicitly_unavailable() -> None:
    canonical = visual_canonical()
    projection = PageProjectionActionizer().action(
        request=projection_request(
            canonical,
            include_figure_captions=True,
        )
    )
    result = PageProjectionEvidenceEnrichmentActionizer().action(
        request=PageProjectionEvidenceEnrichmentRequest(projection=projection)
    )
    entries = tuple(result.entries)
    caption_chunk_source = tuple(next(iter(projection.pages)).blocks)[1]

    assert len(entries) == projection.pages.block_count == 2
    assert result.entries.available_count == 1
    assert result.entries.unavailable_count == 1
    unavailable = entries[1]
    assert type(unavailable) is PageProjectionEvidenceUnavailable
    assert (
        unavailable.source_evidence_id == caption_chunk_source.source_id.value
    )
    assert unavailable.reason is (
        PageProjectionEvidenceUnavailableReason.FIGURE_CAPTION_HAS_NO_EXACT_RAW_CLEAN_PAIR
    )
    assert tuple(value.code.value for value in unavailable.limitations) == (
        "unreviewed_visual_evidence",
    )
    assert not hasattr(unavailable, "retained_text")


def test__evidence_enrichment__retains_opaque_warning_without_detail() -> None:
    canonical = paragraph_canonical()
    source_block = next(iter(next(iter(canonical.document.pages)).blocks))
    assert type(source_block) is ReadingTextEvidenceBlock
    source = next(iter(source_block.sources))
    span = next(iter(source.source_spans))
    warning_id = canonical.request.document.source_id.__class__(
        kind=ReadingEvidenceIdentityKind.WARNING,
        value="warning:opaque",
    )
    warned_span = ReadingSourceSpanEvidence(
        source_id=span.source_id,
        page_location=span.page_location,
        source_object_id=span.source_object_id,
        bounding_box=None,
        geometry_warning_id=warning_id,
        start_offset=span.start_offset,
        end_offset=span.end_offset,
    )
    warned_source = replace(
        source,
        source_spans=ReadingSourceSpanEvidenceInventory(warned_span),
        warning_ids=ReadingEvidenceIdentityInventory(
            ReadingEvidenceIdentityKind.WARNING,
            warning_id,
        ),
    )
    warned_block = ReadingTextEvidenceBlock(
        structured_item=source_block.structured_item,
        sources=ReadingTextBlockSourceInventory(warned_source),
        basis=source_block.basis,
    )

    warning = next(
        iter(derive_page_projection_text_warning_inventory(block=warned_block))
    )

    assert warning.warning_id == warning_id.value
    assert tuple(warning.affected_ids) == (warned_span.span_id.value,)
    assert warning.detail_status is (
        PageProjectionEvidenceWarningDetailStatus.UNAVAILABLE
    )
    assert warning.detail is None


def test__evidence_enrichment__rejects_stale_request_identity() -> None:
    result = enrich_paragraph()
    request = result.request
    object.__setattr__(request, "request_id", "tampered-request-id")

    with pytest.raises(
        PageProjectionError,
        match="request identity is stale",
    ):
        PageProjectionEvidenceEnrichmentActionizer().action(request=request)

    with pytest.raises(
        PageProjectionError,
        match="request identity is stale",
    ):
        PageProjectionEvidenceEnrichmentResult(
            request=request,
            entries=result.entries,
            processor_id=result.processor_id,
            processor_version=result.processor_version,
        )


def test__evidence_enrichment__result_rejects_changed_entry() -> None:
    result = enrich_paragraph()
    entry = next(iter(result.entries))
    assert type(entry) is PageProjectionEvidenceEnrichment
    changed = replace(entry, retained_text="Changed retained text.")

    with pytest.raises(
        PageProjectionError,
        match="differ from deterministic derivation",
    ):
        PageProjectionEvidenceEnrichmentResult(
            request=result.request,
            entries=PageProjectionEvidenceEnrichmentInventory(changed),
            processor_id=result.processor_id,
            processor_version=result.processor_version,
        )

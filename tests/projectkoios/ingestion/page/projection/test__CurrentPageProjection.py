from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from projectkoios.base import (
    DataObjectActionizer,
    DataObjectActionRequest,
    DataObjectActionResult,
)
from projectkoios.ingestion.artifact.managed.verification.evidence import (
    ManagedArtifactVerificationEvidence,
    ManagedArtifactVerificationEvidenceInventory,
)
from projectkoios.ingestion.artifact.managed.verification.request import (
    ManagedArtifactVerificationRequest,
)
from projectkoios.ingestion.artifact.managed.verification.result import (
    ManagedArtifactVerificationResult,
)
from projectkoios.ingestion.page.projection.actionizer import (
    PageProjectionActionizer,
)
from projectkoios.ingestion.page.projection.block import (
    PageProjectionTextBlockInventory,
    PageProjectionTextBlockStyle,
)
from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.limitation import (
    PageProjectionLimitation,
    PageProjectionLimitationInventory,
)
from projectkoios.ingestion.page.projection.page import (
    PageProjectionPage,
    PageProjectionPageInventory,
)
from projectkoios.ingestion.page.projection.request import (
    PageProjectionRequest,
)
from projectkoios.ingestion.page.projection.result import PageProjectionResult
from projectkoios.ingestion.page.projection.window import (
    PageProjectionPageWindowInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.block.equation.evidence import (  # noqa: E501
    ReadingEquationEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.figure.evidence import (  # noqa: E501
    ReadingFigureEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.inventory import (
    ReadingEvidenceBlockInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.block.table.evidence import (  # noqa: E501
    ReadingTableEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.evidence import (  # noqa: E501
    ReadingTextEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.caption.evidence import (  # noqa: E501
    ReadingCaptionEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.document.definition import (  # noqa: E501
    ReadingEvidenceDocument,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.evidence import (  # noqa: E501
    ReadingFigureProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.inventory import (  # noqa: E501
    ReadingFigureProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.inventory import (  # noqa: E501
    ReadingStructuredItemProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.kind import (  # noqa: E501
    ReadingStructuredItemKind,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.definition import (  # noqa: E501
    ReadingEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.page.evidence import (
    ReadingEvidencePage,
)
from projectkoios.ingestion.transcript.reading.evidence.page.inventory import (
    ReadingEvidencePageInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.actionizer import (  # noqa: E501
    ReadingEvidenceProjectionActionizer,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.identity import (  # noqa: E501
    ReadingEvidenceProjectionIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.result import (  # noqa: E501
    ReadingEvidenceProjectionResult,
)
from projectkoios.ingestion.transcript.reading.evidence.source.request import (
    ReadingEvidenceSourceRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.source.result import (
    ReadingEvidenceSourceResult,
)

from tests.projectkoios.ingestion.page.projection.fixture import (
    PageProjectionMixedVisualFixture,
    PageProjectionObservationFixture,
)
from tests.projectkoios.ingestion.transcript.reading.evidence.projection.fixture import (  # noqa: E501
    ReadingEvidenceProjectionFixture,
)
from tests.projectkoios.ingestion.transcript.reading.evidence.projection.visual_fixture import (  # noqa: E501
    ReadingVisualProjectionFixture,
)

_PROVIDER_ID = "page-projection-test-provider:1.0"
_VERIFIER_ID = "page-projection-test-verifier:1.0"
_AUTHORITY_ID = "page-projection-test-authority"
_SOURCE_PROVIDER_ID = "page-projection-test-source-provider:1.0"
_SOURCE_VERIFICATION_ID = "page-projection-test-source-verification"


def verified_artifacts(
    canonical: ReadingEvidenceProjectionResult,
) -> ManagedArtifactVerificationResult:
    references = canonical.document.managed_artifacts
    request = ManagedArtifactVerificationRequest(
        references=references,
        provider_implementation_id=_PROVIDER_ID,
        authority_id=_AUTHORITY_ID,
        maximum_artifact_bytes=max(
            reference.byte_length for reference in references
        ),
        maximum_aggregate_bytes=references.aggregate_byte_length,
        stream_chunk_bytes=1,
    )
    evidence = ManagedArtifactVerificationEvidenceInventory(
        references,
        *(
            ManagedArtifactVerificationEvidence(
                reference=reference,
                observed_sha256=reference.sha256,
                observed_byte_length=reference.byte_length,
                observed_media_type=reference.media_type,
                provider_implementation_id=_PROVIDER_ID,
                verifier_implementation_id=_VERIFIER_ID,
            )
            for reference in references
        ),
    )
    return ManagedArtifactVerificationResult(
        request=request,
        evidence=evidence,
        verifier_implementation_id=_VERIFIER_ID,
    )


def reading_source_result(
    canonical: ReadingEvidenceProjectionResult,
    *,
    document: ReadingEvidenceDocument | None = None,
) -> ReadingEvidenceSourceResult:
    source_document = canonical.document if document is None else document
    inventory = ReadingEvidenceInventory.observe(source_document)
    measures = inventory.measures
    request = ReadingEvidenceSourceRequest(
        provider_source_id="page-projection-test-source",
        document_id=source_document.document_id,
        projection_result_id=canonical.result_id,
        inventory_id=inventory.inventory_id,
        maximum_page_count=max(measures.page_count, 1),
        maximum_block_count=max(measures.block_count, 1),
        maximum_artifact_count=max(measures.artifact_count, 1),
        maximum_provider_record_count=max(measures.block_count, 1),
        authority_id=_AUTHORITY_ID,
    )
    return ReadingEvidenceSourceResult(
        request=request,
        document=source_document,
        inventory=inventory,
        projection_result_id=canonical.result_id,
        provider_implementation_id=_SOURCE_PROVIDER_ID,
        provider_verification_id=_SOURCE_VERIFICATION_ID,
    )


def projection_request(
    canonical: ReadingEvidenceProjectionResult,
    *,
    include_figure_captions: bool,
) -> PageProjectionRequest:
    return PageProjectionRequest(
        source_result=reading_source_result(canonical),
        artifact_verification_result=verified_artifacts(canonical),
        include_figure_captions=include_figure_captions,
    )


def paragraph_canonical() -> ReadingEvidenceProjectionResult:
    fixture = ReadingEvidenceProjectionFixture.build()
    return ReadingEvidenceProjectionActionizer().action(request=fixture.request)


def visual_canonical() -> ReadingEvidenceProjectionResult:
    fixture = ReadingVisualProjectionFixture.build()
    return ReadingEvidenceProjectionActionizer().action(request=fixture.request)


def request_for_document(
    canonical: ReadingEvidenceProjectionResult,
    *,
    document: ReadingEvidenceDocument,
    include_figure_captions: bool,
) -> PageProjectionRequest:
    return PageProjectionRequest(
        source_result=reading_source_result(canonical, document=document),
        artifact_verification_result=verified_artifacts(canonical),
        include_figure_captions=include_figure_captions,
    )


def test__page_projection__is_pure_deterministic_action_contract() -> None:
    request = projection_request(
        paragraph_canonical(), include_figure_captions=False
    )
    actionizer = PageProjectionActionizer()

    first = actionizer.action(request=request)
    second = actionizer.action(request=request)

    assert isinstance(request, DataObjectActionRequest)
    assert isinstance(actionizer, DataObjectActionizer)
    assert isinstance(first, DataObjectActionResult)
    assert first == second
    assert first.request is request
    assert first.document_id == request.source_result.document.document_id
    assert first.source_id == request.source_result.document.source_id
    assert (
        first.projection_result_id == request.source_result.projection_result_id
    )
    assert (
        first.reading_inventory_id
        == request.source_result.inventory.inventory_id
    )
    assert first.source_result_id == request.source_result.result_id
    assert (
        first.artifact_verification_result_id
        == request.artifact_verification_result.result_id
    )
    assert not hasattr(first, "path")
    assert not hasattr(first, "content")


def test__page_projection__omits_table_equation_and_media_text() -> None:
    fixture = PageProjectionMixedVisualFixture.build()
    source_blocks = tuple(next(iter(fixture.document.pages)).blocks)

    result = PageProjectionActionizer().action(
        request=request_for_document(
            fixture.canonical,
            document=fixture.document,
            include_figure_captions=True,
        )
    )

    assert tuple(type(block) for block in source_blocks) == (
        ReadingTextEvidenceBlock,
        ReadingFigureEvidenceBlock,
        ReadingTableEvidenceBlock,
        ReadingEquationEvidenceBlock,
    )
    projected = tuple(next(iter(result.pages)).blocks)
    assert tuple(block.style for block in projected) == (
        PageProjectionTextBlockStyle.PARAGRAPH,
        PageProjectionTextBlockStyle.FIGURE_CAPTION,
    )
    assert tuple(block.text for block in projected) == (
        "Canonical paragraph.",
        "Figure title",
    )


def test__page_projection_observation__matches_frozen_fixture() -> None:
    mixed = PageProjectionMixedVisualFixture.build()
    result = PageProjectionActionizer().action(
        request=request_for_document(
            mixed.canonical,
            document=mixed.document,
            include_figure_captions=True,
        )
    )
    observation = PageProjectionObservationFixture(result=result)
    fixture_path = (
        Path(__file__).parents[4]
        / "fixtures"
        / "page_projection"
        / "current-schema-v1.json"
    )

    fixture_bytes = fixture_path.read_bytes()
    assert fixture_bytes == observation.canonical_bytes()
    assert not fixture_bytes.endswith(b"\n")


def test__page_projection__preserves_exact_paragraph_and_location() -> None:
    canonical = paragraph_canonical()
    result = PageProjectionActionizer().action(
        request=projection_request(canonical, include_figure_captions=False)
    )

    source_page = next(iter(canonical.document.pages))
    source_block = next(iter(source_page.blocks))
    assert type(source_block) is ReadingTextEvidenceBlock
    page = next(iter(result.pages))
    block = next(iter(page.blocks))

    assert page.source_page_id == source_page.page_id
    assert page.page_location == source_page.page_location
    assert page.physical_page_number == 1
    assert page.printed_page_label == "1"
    assert block.order_index == source_block.order_index
    assert block.text == source_block.text == "Canonical paragraph."
    assert block.style is PageProjectionTextBlockStyle.PARAGRAPH
    assert block.source_id == source_block.block_id


def test__page_projection__preserves_heading_style() -> None:
    canonical = paragraph_canonical()
    document = canonical.document
    source_page = next(iter(document.pages))
    text_block = next(iter(source_page.blocks))
    assert type(text_block) is ReadingTextEvidenceBlock
    heading_item = replace(
        text_block.structured_item,
        kind=ReadingStructuredItemKind.HEADING,
    )
    heading_block = ReadingTextEvidenceBlock(
        structured_item=heading_item,
        sources=text_block.sources,
        basis=text_block.basis,
    )
    heading_page = ReadingEvidencePage(
        page_text=source_page.page_text,
        blocks=ReadingEvidenceBlockInventory(heading_block),
    )
    heading_lineage = replace(
        document.lineage,
        structured_item_inventory_id=(
            ReadingEvidenceProjectionIdentityDerivation.derive_inventory(
                role="structured_items",
                identities=[heading_item.record_id.value],
            )
        ),
    )
    heading_document = replace(
        document,
        pages=ReadingEvidencePageInventory(heading_page),
        lineage=heading_lineage,
    )

    result = PageProjectionActionizer().action(
        request=request_for_document(
            canonical,
            document=heading_document,
            include_figure_captions=False,
        )
    )

    projected = next(iter(next(iter(result.pages)).blocks))
    assert projected.text == heading_block.text
    assert projected.style is PageProjectionTextBlockStyle.HEADING
    assert projected.source_id == heading_block.block_id


def test__page_projection__emits_configured_caption_once() -> None:
    canonical = visual_canonical()
    request = projection_request(canonical, include_figure_captions=True)

    result = PageProjectionActionizer().action(request=request)
    blocks = tuple(next(iter(result.pages)).blocks)
    source_figure = tuple(next(iter(canonical.document.pages)).blocks)[1]

    assert len(blocks) == 2
    assert tuple(value.order_index for value in blocks) == (0, 1)
    assert blocks[1].text == "Figure title"
    assert blocks[1].style is PageProjectionTextBlockStyle.FIGURE_CAPTION
    assert type(source_figure) is ReadingFigureEvidenceBlock
    assert source_figure.caption is not None
    assert blocks[1].source_id == source_figure.caption.caption_id
    assert request.artifact_verification_result.evidence


def test__page_projection__omits_caption_when_policy_is_false() -> None:
    canonical = visual_canonical()

    result = PageProjectionActionizer().action(
        request=projection_request(canonical, include_figure_captions=False)
    )

    blocks = tuple(next(iter(result.pages)).blocks)
    assert len(blocks) == 1
    assert blocks[0].style is PageProjectionTextBlockStyle.PARAGRAPH


def test__caption_policy__changes_request_and_result_identity() -> None:
    canonical = visual_canonical()
    excluded_request = projection_request(
        canonical, include_figure_captions=False
    )
    included_request = projection_request(
        canonical, include_figure_captions=True
    )

    excluded = PageProjectionActionizer().action(request=excluded_request)
    included = PageProjectionActionizer().action(request=included_request)

    assert excluded_request.request_id != included_request.request_id
    assert excluded.result_id != included.result_id
    assert excluded.pages.inventory_id != included.pages.inventory_id


def test__request__requires_exact_bool_and_fresh_source_result() -> None:
    canonical = paragraph_canonical()
    request = projection_request(canonical, include_figure_captions=False)

    with pytest.raises(TypeError, match="exact bool"):
        replace(request, include_figure_captions=cast(bool, 1))
    object.__setattr__(
        request.source_result,
        "result_id",
        f"reading-evidence-source-result:sha256:{'e' * 64}",
    )
    with pytest.raises(PageProjectionError, match="source result identities"):
        replace(request)


def test__action__rejects_post_construction_request_mutation() -> None:
    request = projection_request(
        visual_canonical(),
        include_figure_captions=False,
    )
    object.__setattr__(request, "include_figure_captions", True)

    with pytest.raises(PageProjectionError, match="request identity is stale"):
        PageProjectionActionizer().action(request=request)


def test__result__rejects_post_construction_request_mutation() -> None:
    request = projection_request(
        visual_canonical(),
        include_figure_captions=False,
    )
    valid = PageProjectionActionizer().action(request=request)
    object.__setattr__(request, "include_figure_captions", True)

    with pytest.raises(PageProjectionError, match="request identity is stale"):
        PageProjectionResult(
            request=request,
            pages=valid.pages,
            limitations=valid.limitations,
            reading_evidence_limitations=(valid.reading_evidence_limitations),
            processor_id=valid.processor_id,
            processor_version=valid.processor_version,
        )


def test__action__rejects_equal_length_text_with_stale_block_identity() -> None:
    request = projection_request(
        paragraph_canonical(),
        include_figure_captions=False,
    )
    block = next(iter(next(iter(request.source_result.document.pages)).blocks))
    assert type(block) is ReadingTextEvidenceBlock
    original_block_id = block.block_id
    object.__setattr__(block, "text", "Xanonical paragraph.")
    assert block.block_id == original_block_id

    with pytest.raises(
        PageProjectionError,
        match="canonical page projection evidence identities are stale",
    ):
        PageProjectionActionizer().action(request=request)


def test__request__rejects_stale_verification_identity() -> None:
    canonical = paragraph_canonical()
    verification = verified_artifacts(canonical)
    object.__setattr__(
        verification,
        "result_id",
        f"managed-artifact-verification-result:sha256:{'f' * 64}",
    )

    with pytest.raises(PageProjectionError, match="stale"):
        PageProjectionRequest(
            source_result=reading_source_result(canonical),
            artifact_verification_result=verification,
            include_figure_captions=False,
        )


def test__request__rejects_verification_for_different_references() -> None:
    canonical = paragraph_canonical()

    with pytest.raises(PageProjectionError, match="different references"):
        PageProjectionRequest(
            source_result=reading_source_result(canonical),
            artifact_verification_result=verified_artifacts(visual_canonical()),
            include_figure_captions=False,
        )


def test__projection__rejects_caption_matching_emitted_text() -> None:
    canonical = visual_canonical()
    document = canonical.document
    source_page = next(iter(document.pages))
    text_block, figure_block = tuple(source_page.blocks)
    assert type(text_block) is ReadingTextEvidenceBlock
    assert type(figure_block) is ReadingFigureEvidenceBlock
    assert figure_block.caption is not None
    duplicate_caption = ReadingCaptionEvidence(
        text=f"  {text_block.text}\n",
        association_ids=figure_block.caption.association_ids,
        basis=figure_block.caption.basis,
    )
    replacement_figure = ReadingFigureEvidenceBlock(
        structured_item=figure_block.structured_item,
        producer_evidence=figure_block.producer_evidence,
        caption=duplicate_caption,
    )
    replacement_page = ReadingEvidencePage(
        page_text=source_page.page_text,
        blocks=ReadingEvidenceBlockInventory(
            text_block,
            replacement_figure,
        ),
    )
    replacement_document = replace(
        document,
        pages=ReadingEvidencePageInventory(replacement_page),
    )
    request = request_for_document(
        canonical,
        document=replacement_document,
        include_figure_captions=True,
    )

    with pytest.raises(PageProjectionError, match="duplicates projected text"):
        PageProjectionActionizer().action(request=request)


def test__projection__rejects_duplicate_caption_identity() -> None:
    canonical = visual_canonical()
    document = canonical.document
    source_page = next(iter(document.pages))
    text_block, figure_block = tuple(source_page.blocks)
    assert type(text_block) is ReadingTextEvidenceBlock
    assert type(figure_block) is ReadingFigureEvidenceBlock
    foundation = ReadingEvidenceProjectionFixture.build().foundation
    duplicate_object_id = foundation.identity(
        ReadingEvidenceIdentityKind.SOURCE_OBJECT,
        "duplicate-figure",
    )
    duplicate_producer = ReadingFigureProducerEvidence(
        candidate_id=foundation.identity(
            ReadingEvidenceIdentityKind.CANDIDATE,
            "duplicate-figure",
        ),
        lineage=foundation.producer_lineage(
            source_object_id=duplicate_object_id,
        ),
        assessment=figure_block.producer_evidence.assessment,
    )
    duplicate_item = ReadingStructuredItemProducerEvidence(
        page_location=figure_block.structured_item.page_location,
        order_index=2,
        kind=figure_block.structured_item.kind,
        source_block_ids=figure_block.structured_item.source_block_ids,
        source_object_id=duplicate_object_id,
        producer_id=figure_block.structured_item.producer_id,
        producer_version=figure_block.structured_item.producer_version,
    )
    duplicate_figure = ReadingFigureEvidenceBlock(
        structured_item=duplicate_item,
        producer_evidence=duplicate_producer,
        caption=figure_block.caption,
    )
    replacement_page = ReadingEvidencePage(
        page_text=source_page.page_text,
        blocks=ReadingEvidenceBlockInventory(
            text_block,
            figure_block,
            duplicate_figure,
        ),
    )
    structured_inventory = ReadingStructuredItemProducerEvidenceInventory(
        text_block.structured_item,
        figure_block.structured_item,
        duplicate_item,
    )
    retained_figures = ReadingFigureProducerEvidenceInventory(
        *sorted(
            (figure_block.producer_evidence, duplicate_producer),
            key=lambda value: value.record_id.value,
        )
    )
    replacement_lineage = replace(
        document.lineage,
        structured_item_inventory_id=(
            ReadingEvidenceProjectionIdentityDerivation.derive_inventory(
                role="structured_items",
                identities=structured_inventory.identity_material(),
            )
        ),
        figure_inventory_id=(
            ReadingEvidenceProjectionIdentityDerivation.derive_inventory(
                role="figures",
                identities=retained_figures.identity_material(),
            )
        ),
    )
    replacement_document = replace(
        document,
        pages=ReadingEvidencePageInventory(replacement_page),
        retained_figures=retained_figures,
        lineage=replacement_lineage,
    )
    request = request_for_document(
        canonical,
        document=replacement_document,
        include_figure_captions=True,
    )

    with pytest.raises(PageProjectionError, match="identity is duplicated"):
        PageProjectionActionizer().action(request=request)

    excluded = PageProjectionActionizer().action(
        request=request_for_document(
            canonical,
            document=replacement_document,
            include_figure_captions=False,
        )
    )
    assert len(tuple(next(iter(excluded.pages)).blocks)) == 1


def test__result__retains_distinct_upstream_and_scope_limitations() -> None:
    canonical = visual_canonical()

    result = PageProjectionActionizer().action(
        request=projection_request(canonical, include_figure_captions=True)
    )

    assert result.reading_evidence_limitations == canonical.document.limitations
    assert tuple(result.limitations) == tuple(PageProjectionLimitation)
    assert len(result.limitations) == 6


def test__result__rejects_forged_page_derivation() -> None:
    canonical = paragraph_canonical()
    request = projection_request(canonical, include_figure_captions=False)
    derived = PageProjectionActionizer().action(request=request)
    source_page = next(iter(canonical.document.pages))
    forged_page = PageProjectionPage(
        source_page_id=source_page.page_id,
        page_location=source_page.page_location,
        blocks=PageProjectionTextBlockInventory(),
    )

    with pytest.raises(PageProjectionError, match="deterministic projection"):
        replace(
            derived,
            pages=PageProjectionPageInventory(forged_page),
        )


def test__page_windows__preserve_pages_and_projection_identity() -> None:
    foundation = ReadingEvidenceProjectionFixture.build().foundation
    pages = PageProjectionPageInventory(
        *(
            PageProjectionPage(
                source_page_id=foundation.identity(
                    ReadingEvidenceIdentityKind.EVIDENCE_PAGE,
                    f"page-{index}",
                ),
                page_location=ReadingPageLocation(
                    physical_page_index=index,
                    printed_page_label=str(index + 1),
                ),
                blocks=PageProjectionTextBlockInventory(),
            )
            for index in range(3)
        )
    )

    windows = PageProjectionPageWindowInventory(pages=pages, window_size=2)

    assert tuple(len(value) for value in windows) == (2, 1)
    assert tuple(page for window in windows for page in window) == tuple(pages)
    assert windows.source_inventory_id == pages.inventory_id
    assert all(page.page_id for page in pages)


def test__limitation_inventory__is_mandatory_and_deterministic() -> None:
    first = PageProjectionLimitationInventory()
    second = PageProjectionLimitationInventory()

    assert first == second
    assert first.inventory_id == second.inventory_id
    assert tuple(first) == tuple(PageProjectionLimitation)

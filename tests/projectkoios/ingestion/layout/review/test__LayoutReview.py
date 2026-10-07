from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest
from projectkoios.ingestion.integrations.layout_parser.actionizer import (
    LayoutParserRegionProposalActionizer,
)
from projectkoios.ingestion.integrations.layout_parser.configuration import (
    LayoutParserProposalConfiguration,
)
from projectkoios.ingestion.integrations.layout_parser.detection import (
    LayoutParserDetection,
)
from projectkoios.ingestion.integrations.layout_parser.request import (
    LayoutParserProposalRequest,
)
from projectkoios.ingestion.layout.annotation.collection import (
    LayoutAnnotationCollection,
)
from projectkoios.ingestion.layout.annotation.failure import (
    LayoutFailureAnnotation,
)
from projectkoios.ingestion.layout.annotation.kind import (
    LayoutAnnotationOutcome,
    LayoutFailureKind,
)
from projectkoios.ingestion.layout.annotation.order import (
    LayoutReadingOrderAnnotation,
)
from projectkoios.ingestion.layout.annotation.region import (
    LayoutRegionAnnotation,
)
from projectkoios.ingestion.layout.contracts import (
    DeterministicLayoutProcessor,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.render.evidence import (
    LayoutPageRenderEvidence,
)
from projectkoios.ingestion.layout.review.actionizer import (
    DeterministicLayoutReviewActionizer,
)
from projectkoios.ingestion.layout.review.configuration import (
    LayoutReviewConfiguration,
)
from projectkoios.ingestion.layout.review.kind import LayoutReviewReason
from projectkoios.ingestion.layout.review.request import LayoutReviewRequest
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedPage,
    SourceDocument,
    SourceSpan,
)
from projectkoios.ingestion.pdf.models import PYMUPDF_COORDINATE_SYSTEM
from projectkoios.ingestion.serialization import serialize_contract
from projectkoios.ingestion.sha256.hash import SHA256Hash


def source_page() -> tuple[SourceDocument, ExtractedPage]:
    source = SourceDocument.from_bytes(
        b"layout review fixture",
        source_id="fixture:layout-review",
        media_type="application/pdf",
        locator="fixture://layout-review.pdf",
    )
    blocks = tuple(
        ExtractedBlock.create(
            kind="text",
            source_spans=(
                SourceSpan(
                    source_id=source.source_id,
                    source_blob_id=source.blob_id,
                    page_index=0,
                    source_object_id=f"block:{ordinal}",
                    bounding_box=box,
                ),
            ),
            extraction_method="fixture",
            confidence=1.0,
            text=f"block {ordinal}",
        )
        for ordinal, box in (
            (1, (10.0, 10.0, 40.0, 20.0)),
            (2, (10.0, 40.0, 40.0, 50.0)),
        )
    )
    page = ExtractedPage(
        page_index=0,
        width=100.0,
        height=100.0,
        blocks=blocks,
        coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
    )
    return source, page


def render_evidence() -> tuple[
    SourceDocument, ExtractedPage, LayoutPageRenderEvidence
]:
    source, page = source_page()
    layout = DeterministicLayoutProcessor().analyze_page(source, page)
    render = LayoutPageRenderEvidence.create(
        layout=layout,
        image_width=200,
        image_height=200,
        image_media_type="image/png",
        image_sha256="a" * 64,
        renderer_name="fixture-renderer",
        renderer_version="1",
        renderer_configuration_id="fixture-renderer:scale-2",
    )
    return source, page, render


def layout_parser_configuration() -> LayoutParserProposalConfiguration:
    return LayoutParserProposalConfiguration(
        package_version="0.3.4",
        backend_name="effdet",
        backend_version="0.4.1",
        model_identity="layoutparser/efficientdet:PubLayNet/d0",
        model_sha256=SHA256Hash("b" * 64),
        label_mapping=(
            ("Figure", LayoutRegionKind.FIGURE),
            ("List", LayoutRegionKind.LIST),
            ("Table", LayoutRegionKind.TABLE),
            ("Text", LayoutRegionKind.TEXT),
            ("Title", LayoutRegionKind.TITLE),
        ),
    )


def prepared_case():
    source, page, render = render_evidence()
    detection = LayoutParserDetection.create(
        render_id=render.render_id,
        label="Text",
        bounding_box_pixels=(20.0, 20.0, 80.0, 40.0),
        confidence=0.95,
    )
    adapter_request = LayoutParserProposalRequest.create(
        render=render,
        detections=(detection,),
        configuration=layout_parser_configuration(),
    )
    adapter_result = LayoutParserRegionProposalActionizer().action(
        request=adapter_request
    )
    layout = DeterministicLayoutProcessor().analyze_page(source, page)
    review_request = LayoutReviewRequest.create(
        layout=layout,
        render=render,
        proposal_source=adapter_result.proposal_source,
        proposals=adapter_result.proposals,
        configuration=LayoutReviewConfiguration(
            minimum_block_intersection_ratio=0.5,
            minimum_page_coverage_ratio=0.9,
        ),
    )
    review_case = DeterministicLayoutReviewActionizer().action(
        request=review_request
    )
    return page, adapter_result, review_request, review_case


def test__layout_parser_adapter__retains_lineage_without_vendor_import() -> (
    None
):
    _, adapter_result, _, _ = prepared_case()

    assert adapter_result.proposal_source.detector_name == "layoutparser:effdet"
    assert adapter_result.proposal_source.resource_sha256 == "b" * 64
    assert len(adapter_result.proposals) == 1
    assert adapter_result.proposals[0].kind is LayoutRegionKind.TEXT
    assert dict(adapter_result.proposals[0].evidence)["model_label"] == "Text"


def test__layout_review__selects_incomplete_region_coverage() -> None:
    page, _, request, review_case = prepared_case()

    assert review_case.covered_block_ids == (page.blocks[0].block_id,)
    assert review_case.uncovered_block_ids == (page.blocks[1].block_id,)
    assert review_case.invalid_geometry_block_ids == ()
    assert review_case.page_coverage_ratio == 0.5
    assert review_case.reasons == (
        LayoutReviewReason.INCOMPLETE_REGION_COVERAGE,
    )
    assert review_case.requires_review is True
    assert review_case == DeterministicLayoutReviewActionizer().action(
        request=request
    )


def test__layout_annotation__records_correction_without_accepting_it() -> None:
    page, adapter_result, _, review_case = prepared_case()
    region = LayoutRegionAnnotation.create(
        case_id=review_case.case_id,
        kind=LayoutRegionKind.TEXT,
        bounding_box_pixels=(20.0, 20.0, 80.0, 100.0),
        block_ids=tuple(block.block_id for block in page.blocks),
    )
    order = LayoutReadingOrderAnnotation.create(
        case_id=review_case.case_id,
        before_block_id=page.blocks[0].block_id,
        after_block_id=page.blocks[1].block_id,
    )
    failure = LayoutFailureAnnotation.create(
        case_id=review_case.case_id,
        kind=LayoutFailureKind.MISSED_REGION,
        block_ids=(page.blocks[1].block_id,),
        proposal_ids=(adapter_result.proposals[0].proposal_id,),
        region_annotation_ids=(region.region_annotation_id,),
    )

    annotation = LayoutAnnotationCollection.create(
        case=review_case,
        annotator_id="fixture-annotator",
        outcome=LayoutAnnotationOutcome.CORRECTION_PROPOSED,
        regions=(region,),
        order_edges=(order,),
        failures=(failure,),
        evidence=(("review", "fixture"),),
    )

    assert annotation.case_id == review_case.case_id
    assert annotation.outcome is LayoutAnnotationOutcome.CORRECTION_PROPOSED
    assert annotation.failures == (failure,)
    assert serialize_contract(annotation) == serialize_contract(annotation)
    with pytest.raises(FrozenInstanceError):
        annotation.annotator_id = "changed"  # type: ignore[misc]


def test__layout_annotation__rejects_cyclic_order() -> None:
    page, _, _, review_case = prepared_case()
    forward = LayoutReadingOrderAnnotation.create(
        case_id=review_case.case_id,
        before_block_id=page.blocks[0].block_id,
        after_block_id=page.blocks[1].block_id,
    )
    backward = LayoutReadingOrderAnnotation.create(
        case_id=review_case.case_id,
        before_block_id=page.blocks[1].block_id,
        after_block_id=page.blocks[0].block_id,
    )

    with pytest.raises(ValueError, match="cycle"):
        LayoutAnnotationCollection.create(
            case=review_case,
            annotator_id="fixture-annotator",
            outcome=LayoutAnnotationOutcome.CORRECTION_PROPOSED,
            order_edges=(forward, backward),
        )


def test__layout_parser_request__rejects_unmapped_label() -> None:
    _, _, render = render_evidence()
    detection = LayoutParserDetection.create(
        render_id=render.render_id,
        label="Equation",
        bounding_box_pixels=(20.0, 20.0, 80.0, 40.0),
        confidence=0.95,
    )

    with pytest.raises(ValueError, match="not mapped"):
        LayoutParserProposalRequest.create(
            render=render,
            detections=(detection,),
            configuration=layout_parser_configuration(),
        )


def test__layout_review_contracts__reject_stale_identities() -> None:
    _, adapter_result, _, review_case = prepared_case()

    with pytest.raises(ValueError, match="inconsistent"):
        replace(review_case, case_id="layout-review-case:sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="inconsistent"):
        replace(review_case, layout_result_id="page-layout-result:stale")
    with pytest.raises(ValueError, match="inconsistent"):
        replace(review_case, proposal_source_id="layout-proposal-source:stale")
    with pytest.raises(ValueError, match="inconsistent"):
        replace(
            review_case,
            proposal_ids=review_case.proposal_ids + ("layout-proposal:stale",),
        )
    with pytest.raises(ValueError, match="inconsistent"):
        replace(
            adapter_result.proposals[0],
            proposal_id="layout-region-proposal:sha256:" + "0" * 64,
        )

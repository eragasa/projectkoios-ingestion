from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.ingestion.integrations.docling.layout.reading.actionizer import (  # noqa: E501
    DoclingReadingOrderActionizer,
)
from projectkoios.ingestion.integrations.docling.layout.reading.configuration import (  # noqa: E501
    DoclingReadingOrderConfiguration,
)
from projectkoios.ingestion.integrations.docling.layout.reading.provider import (  # noqa: E501
    InstalledDoclingReadingOrderProvider,
)
from projectkoios.ingestion.integrations.docling.layout.reading.request import (
    DoclingReadingOrderRequest,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.reading.order.actionizer import (
    DeterministicLayoutReadingOrderActionizer,
)
from projectkoios.ingestion.layout.reading.order.block import (
    LayoutReadingOrderBlock,
    LayoutReadingOrderBlockInventory,
    LayoutReadingOrderExpectedBlockInventory,
)
from projectkoios.ingestion.layout.reading.order.candidate import (
    LayoutReadingOrderCandidate,
    LayoutReadingOrderCandidateElement,
    LayoutReadingOrderCandidateElementInventory,
    LayoutReadingOrderCandidateEvidence,
)
from projectkoios.ingestion.layout.reading.order.configuration import (
    LayoutReadingOrderConfiguration,
)
from projectkoios.ingestion.layout.reading.order.kind import (
    LayoutReadingDirection,
    LayoutReadingOrderReason,
    LayoutReadingOrderStatus,
)
from projectkoios.ingestion.layout.reading.order.reason import (
    LayoutReadingOrderReasonInventory,
)
from projectkoios.ingestion.layout.reading.order.region import (
    LayoutReadingOrderRegion,
    LayoutReadingOrderRegionInventory,
)
from projectkoios.ingestion.layout.reading.order.request import (
    LayoutReadingOrderRequest,
)
from projectkoios.ingestion.layout.reading.order.resolution import (
    LayoutReadingOrderNativeBlockSequence,
    LayoutReadingOrderRegionSequence,
    LayoutReadingOrderResolution,
)
from projectkoios.ingestion.layout.reading.order.result import (
    LayoutReadingOrderResult,
)

from tests.projectkoios.ingestion.layout.review.layout_review_support import (
    LayoutReviewFixture,
)


def block(
    block_id: str,
    box: tuple[float, float, float, float],
) -> LayoutReadingOrderBlock:
    return LayoutReadingOrderBlock(
        block_id=block_id,
        bounding_box_pixels=box,
    )


def region(
    region_id: str,
    kind: LayoutRegionKind,
    box: tuple[float, float, float, float],
    *blocks: LayoutReadingOrderBlock,
) -> LayoutReadingOrderRegion:
    return LayoutReadingOrderRegion(
        region_id=region_id,
        kind=kind,
        bounding_box_pixels=box,
        blocks=LayoutReadingOrderBlockInventory(*blocks),
    )


def resolution_request(
    *,
    regions: tuple[LayoutReadingOrderRegion, ...],
    candidate_ids: tuple[str, ...],
    expected_block_ids: tuple[str, ...] = (),
    direction: LayoutReadingDirection = LayoutReadingDirection.LEFT_TO_RIGHT,
) -> LayoutReadingOrderRequest:
    render = LayoutReviewFixture().render_evidence()[2]
    upstream_evidence_id = "layout-gate:sha256:test"
    elements = LayoutReadingOrderCandidateElementInventory(
        *(
            LayoutReadingOrderCandidateElement(
                region_id=item.region_id,
                source_index=index,
                kind=item.kind,
                bounding_box_pixels=item.bounding_box_pixels,
            )
            for index, item in enumerate(regions)
        )
    )
    candidate_evidence = LayoutReadingOrderCandidateEvidence(
        source_request_id="candidate-request:sha256:test",
        producer_implementation_id="fixture-candidate-producer:1",
        render_id=render.render_id,
        upstream_evidence_id=upstream_evidence_id,
        direction=direction,
        elements=elements,
        candidate=LayoutReadingOrderCandidate(*candidate_ids),
    )
    return LayoutReadingOrderRequest(
        render=render,
        upstream_evidence_id=upstream_evidence_id,
        direction=direction,
        expected_blocks=LayoutReadingOrderExpectedBlockInventory(
            *expected_block_ids
        ),
        regions=LayoutReadingOrderRegionInventory(*regions),
        candidate_evidence=candidate_evidence,
        configuration=LayoutReadingOrderConfiguration(),
    )


def resolve(request: LayoutReadingOrderRequest):
    return DeterministicLayoutReadingOrderActionizer().action(request=request)


def two_column_regions() -> tuple[LayoutReadingOrderRegion, ...]:
    return (
        region(
            "left-top",
            LayoutRegionKind.TEXT,
            (5.0, 10.0, 45.0, 20.0),
            block("block-left-top", (7.0, 12.0, 43.0, 18.0)),
        ),
        region(
            "left-bottom",
            LayoutRegionKind.EQUATION,
            (5.0, 30.0, 45.0, 40.0),
            block("block-left-bottom", (7.0, 32.0, 43.0, 38.0)),
        ),
        region(
            "right-top",
            LayoutRegionKind.FIGURE,
            (55.0, 10.0, 95.0, 20.0),
        ),
        region(
            "right-bottom",
            LayoutRegionKind.TABLE,
            (55.0, 30.0, 95.0, 40.0),
        ),
    )


def test_request_rejects_candidate_page_lineage_drift() -> None:
    request = resolution_request(
        regions=two_column_regions(),
        candidate_ids=("left-top", "left-bottom", "right-top", "right-bottom"),
        expected_block_ids=("block-left-top", "block-left-bottom"),
    )
    drifted = replace(
        request.candidate_evidence,
        render_id="layout-render:sha256:drifted",
    )

    with pytest.raises(ValueError, match="page lineage"):
        replace(request, candidate_evidence=drifted)


@pytest.mark.parametrize(
    ("changes", "expected_message"),
    (
        (
            {"upstream_evidence_id": "layout-gate:sha256:drifted"},
            "page lineage",
        ),
        (
            {"direction": LayoutReadingDirection.RIGHT_TO_LEFT},
            "page lineage",
        ),
    ),
)
def test_request_rejects_candidate_lineage_drift(
    changes: dict[str, object],
    expected_message: str,
) -> None:
    request = resolution_request(
        regions=two_column_regions(),
        candidate_ids=("left-top", "left-bottom", "right-top", "right-bottom"),
        expected_block_ids=("block-left-top", "block-left-bottom"),
    )
    drifted = replace(request.candidate_evidence, **changes)

    with pytest.raises(ValueError, match=expected_message):
        replace(request, candidate_evidence=drifted)


def test_candidate_change_derives_a_distinct_evidence_identity() -> None:
    request = resolution_request(
        regions=two_column_regions(),
        candidate_ids=("left-top", "left-bottom", "right-top", "right-bottom"),
        expected_block_ids=("block-left-top", "block-left-bottom"),
    )
    drifted = replace(
        request.candidate_evidence,
        candidate=LayoutReadingOrderCandidate(
            "left-top",
            "right-top",
            "left-bottom",
            "right-bottom",
        ),
    )

    assert drifted.evidence_id != request.candidate_evidence.evidence_id
    result = resolve(replace(request, candidate_evidence=drifted))
    assert result.status is LayoutReadingOrderStatus.ESCALATION_REQUIRED
    assert LayoutReadingOrderReason.CANDIDATE_GEOMETRY_DISAGREEMENT in tuple(
        result.reasons
    )


@pytest.mark.parametrize(
    "element_changes",
    (
        {"kind": LayoutRegionKind.TITLE},
        {"bounding_box_pixels": (6.0, 10.0, 45.0, 20.0)},
    ),
)
def test_request_rejects_candidate_region_evidence_drift(
    element_changes: dict[str, object],
) -> None:
    request = resolution_request(
        regions=two_column_regions(),
        candidate_ids=("left-top", "left-bottom", "right-top", "right-bottom"),
        expected_block_ids=("block-left-top", "block-left-bottom"),
    )
    elements = tuple(request.candidate_evidence.elements)
    drifted_first = replace(elements[0], **element_changes)
    drifted_evidence = replace(
        request.candidate_evidence,
        elements=LayoutReadingOrderCandidateElementInventory(
            drifted_first,
            *elements[1:],
        ),
    )

    with pytest.raises(ValueError, match="region evidence"):
        replace(request, candidate_evidence=drifted_evidence)


def test_resolves_complete_single_column_geometry() -> None:
    regions = (
        region(
            "title",
            LayoutRegionKind.TITLE,
            (10.0, 10.0, 90.0, 20.0),
            block("title-block", (12.0, 12.0, 88.0, 18.0)),
        ),
        region(
            "text",
            LayoutRegionKind.TEXT,
            (10.0, 30.0, 90.0, 60.0),
            block("text-a", (12.0, 32.0, 88.0, 40.0)),
            block("text-b", (12.0, 45.0, 88.0, 55.0)),
        ),
    )
    request = resolution_request(
        regions=regions,
        candidate_ids=("title", "text"),
        expected_block_ids=("title-block", "text-a", "text-b"),
    )

    result = resolve(request)

    assert result.status is LayoutReadingOrderStatus.RESOLVED
    assert result.resolution is not None
    assert tuple(result.resolution.region_order) == ("title", "text")
    assert tuple(result.resolution.native_block_order) == (
        "title-block",
        "text-a",
        "text-b",
    )


@pytest.mark.parametrize(
    ("direction", "candidate_ids", "expected_region_ids"),
    (
        (
            LayoutReadingDirection.LEFT_TO_RIGHT,
            ("left-top", "left-bottom", "right-top", "right-bottom"),
            ("left-top", "left-bottom", "right-top", "right-bottom"),
        ),
        (
            LayoutReadingDirection.RIGHT_TO_LEFT,
            ("right-top", "right-bottom", "left-top", "left-bottom"),
            ("right-top", "right-bottom", "left-top", "left-bottom"),
        ),
    ),
)
def test_resolves_pure_disjoint_columns_in_configured_direction(
    direction: LayoutReadingDirection,
    candidate_ids: tuple[str, ...],
    expected_region_ids: tuple[str, ...],
) -> None:
    request = resolution_request(
        regions=two_column_regions(),
        candidate_ids=candidate_ids,
        expected_block_ids=("block-left-top", "block-left-bottom"),
        direction=direction,
    )

    result = resolve(request)

    assert result.status is LayoutReadingOrderStatus.RESOLVED
    assert result.resolution is not None
    assert tuple(result.resolution.region_order) == expected_region_ids


def test_escalates_when_docling_candidate_disagrees_with_column_geometry() -> (
    None
):
    regions = two_column_regions()
    request = resolution_request(
        regions=regions,
        candidate_ids=("left-top", "right-top", "left-bottom", "right-bottom"),
        expected_block_ids=("block-left-top", "block-left-bottom"),
    )

    result = resolve(request)

    assert result.status is LayoutReadingOrderStatus.ESCALATION_REQUIRED
    assert tuple(result.reasons) == (
        LayoutReadingOrderReason.CANDIDATE_GEOMETRY_DISAGREEMENT,
    )


def test_resolves_leading_title_that_mechanically_spans_columns() -> None:
    regions = (
        region("title", LayoutRegionKind.TITLE, (5.0, 2.0, 95.0, 8.0)),
        *two_column_regions(),
    )
    request = resolution_request(
        regions=regions,
        candidate_ids=(
            "title",
            "left-top",
            "left-bottom",
            "right-top",
            "right-bottom",
        ),
        expected_block_ids=("block-left-top", "block-left-bottom"),
    )

    result = resolve(request)

    assert result.status is LayoutReadingOrderStatus.RESOLVED
    assert result.resolution is not None
    assert tuple(result.resolution.region_order)[0] == "title"


def test_escalates_lower_spanning_title_after_earlier_narrow_title() -> None:
    regions = (
        region(
            "upper-narrow-title", LayoutRegionKind.TITLE, (5.0, 2.0, 45.0, 8.0)
        ),
        region(
            "lower-spanning-title",
            LayoutRegionKind.TITLE,
            (5.0, 10.0, 95.0, 15.0),
        ),
        *two_column_regions(),
    )
    request = resolution_request(
        regions=regions,
        candidate_ids=(
            "lower-spanning-title",
            "upper-narrow-title",
            "left-top",
            "left-bottom",
            "right-top",
            "right-bottom",
        ),
        expected_block_ids=("block-left-top", "block-left-bottom"),
    )

    result = resolve(request)

    assert result.status is LayoutReadingOrderStatus.ESCALATION_REQUIRED
    assert LayoutReadingOrderReason.SPANNING_REGION_AMBIGUOUS in tuple(
        result.reasons
    )


def test_escalates_spanning_title_inside_column_body() -> None:
    regions = (
        *two_column_regions(),
        region(
            "section-title", LayoutRegionKind.TITLE, (5.0, 22.0, 95.0, 28.0)
        ),
    )
    request = resolution_request(
        regions=regions,
        candidate_ids=(
            "left-top",
            "section-title",
            "left-bottom",
            "right-top",
            "right-bottom",
        ),
        expected_block_ids=("block-left-top", "block-left-bottom"),
    )

    result = resolve(request)

    assert LayoutReadingOrderReason.SPANNING_REGION_AMBIGUOUS in tuple(
        result.reasons
    )


def test_escalates_caption_without_exact_association() -> None:
    caption = region(
        "caption",
        LayoutRegionKind.CAPTION,
        (10.0, 50.0, 90.0, 60.0),
    )
    request = resolution_request(
        regions=(caption,),
        candidate_ids=("caption",),
    )

    result = resolve(request)

    assert tuple(result.reasons) == (
        LayoutReadingOrderReason.CAPTION_ASSOCIATION_REQUIRED,
    )


def test_escalates_footnote_without_exact_association() -> None:
    footnote = region(
        "footnote",
        LayoutRegionKind.FOOTNOTE,
        (10.0, 80.0, 90.0, 90.0),
    )
    request = resolution_request(
        regions=(footnote,),
        candidate_ids=("footnote",),
    )

    result = resolve(request)

    assert tuple(result.reasons) == (
        LayoutReadingOrderReason.FOOTNOTE_ASSOCIATION_REQUIRED,
    )


def test_resolves_explicit_header_body_footer_bands() -> None:
    regions = (
        region("footer", LayoutRegionKind.FOOTER, (10.0, 90.0, 90.0, 95.0)),
        region("body", LayoutRegionKind.TEXT, (10.0, 20.0, 90.0, 70.0)),
        region("header", LayoutRegionKind.HEADER, (10.0, 2.0, 90.0, 7.0)),
    )
    request = resolution_request(
        regions=regions,
        candidate_ids=("header", "body", "footer"),
    )

    result = resolve(request)

    assert result.status is LayoutReadingOrderStatus.RESOLVED
    assert result.resolution is not None
    assert tuple(result.resolution.region_order) == (
        "header",
        "body",
        "footer",
    )


@pytest.mark.parametrize(
    ("case_request", "expected_reason"),
    (
        (
            resolution_request(
                regions=(
                    region(
                        "region",
                        LayoutRegionKind.TEXT,
                        (10.0, 10.0, 90.0, 30.0),
                    ),
                ),
                candidate_ids=("region",),
                expected_block_ids=("missing",),
            ),
            LayoutReadingOrderReason.UNASSIGNED_NATIVE_BLOCK,
        ),
        (
            resolution_request(
                regions=(
                    region(
                        "one",
                        LayoutRegionKind.TEXT,
                        (10.0, 10.0, 90.0, 30.0),
                        block("duplicate", (12.0, 12.0, 88.0, 18.0)),
                    ),
                    region(
                        "two",
                        LayoutRegionKind.TEXT,
                        (10.0, 40.0, 90.0, 60.0),
                        block("duplicate", (12.0, 42.0, 88.0, 48.0)),
                    ),
                ),
                candidate_ids=("one", "two"),
                expected_block_ids=("duplicate",),
            ),
            LayoutReadingOrderReason.DUPLICATE_NATIVE_BLOCK_ASSIGNMENT,
        ),
        (
            resolution_request(
                regions=(
                    region(
                        "region",
                        LayoutRegionKind.TEXT,
                        (10.0, 10.0, 90.0, 30.0),
                        block("unknown", (12.0, 12.0, 88.0, 18.0)),
                    ),
                ),
                candidate_ids=("region",),
            ),
            LayoutReadingOrderReason.UNKNOWN_NATIVE_BLOCK,
        ),
        (
            resolution_request(
                regions=(
                    region(
                        "region",
                        LayoutRegionKind.TEXT,
                        (10.0, 10.0, 40.0, 30.0),
                        block("outside", (20.0, 20.0, 50.0, 25.0)),
                    ),
                ),
                candidate_ids=("region",),
                expected_block_ids=("outside",),
            ),
            LayoutReadingOrderReason.NATIVE_BLOCK_REGION_CONFLICT,
        ),
    ),
)
def test_escalates_incomplete_or_conflicting_block_assignment(
    case_request: LayoutReadingOrderRequest,
    expected_reason: LayoutReadingOrderReason,
) -> None:
    result = resolve(case_request)

    assert expected_reason in tuple(result.reasons)
    assert result.resolution is None


@pytest.mark.parametrize(
    ("case_request", "expected_reason"),
    (
        (
            resolution_request(
                regions=(
                    region(
                        "one",
                        LayoutRegionKind.TEXT,
                        (10.0, 10.0, 90.0, 20.0),
                    ),
                    region(
                        "two",
                        LayoutRegionKind.TEXT,
                        (10.0, 30.0, 90.0, 40.0),
                    ),
                ),
                candidate_ids=("one",),
            ),
            LayoutReadingOrderReason.CANDIDATE_INCOMPLETE,
        ),
        (
            resolution_request(
                regions=(
                    region(
                        "known",
                        LayoutRegionKind.TEXT,
                        (10.0, 10.0, 90.0, 20.0),
                    ),
                ),
                candidate_ids=("unknown",),
            ),
            LayoutReadingOrderReason.CANDIDATE_UNKNOWN_REGION,
        ),
        (
            resolution_request(
                regions=(
                    region(
                        "one",
                        LayoutRegionKind.TEXT,
                        (10.0, 10.0, 90.0, 30.0),
                    ),
                    region(
                        "two",
                        LayoutRegionKind.TEXT,
                        (10.0, 20.0, 90.0, 40.0),
                    ),
                ),
                candidate_ids=("one", "two"),
            ),
            LayoutReadingOrderReason.OVERLAPPING_REGIONS,
        ),
        (
            resolution_request(
                regions=(
                    region(
                        "upper-left",
                        LayoutRegionKind.TEXT,
                        (10.0, 10.0, 40.0, 20.0),
                    ),
                    region(
                        "lower-right",
                        LayoutRegionKind.TEXT,
                        (60.0, 30.0, 90.0, 40.0),
                    ),
                ),
                candidate_ids=("upper-left", "lower-right"),
            ),
            LayoutReadingOrderReason.COLUMN_ORDER_AMBIGUOUS,
        ),
        (
            resolution_request(
                regions=(
                    region(
                        "sidebar",
                        LayoutRegionKind.SIDEBAR,
                        (10.0, 10.0, 90.0, 30.0),
                    ),
                ),
                candidate_ids=("sidebar",),
            ),
            LayoutReadingOrderReason.UNSUPPORTED_REGION_KIND,
        ),
        (
            resolution_request(
                regions=(
                    region(
                        "body",
                        LayoutRegionKind.TEXT,
                        (10.0, 10.0, 90.0, 30.0),
                    ),
                    region(
                        "header",
                        LayoutRegionKind.HEADER,
                        (10.0, 40.0, 90.0, 50.0),
                    ),
                ),
                candidate_ids=("header", "body"),
            ),
            LayoutReadingOrderReason.HEADER_POSITION_CONFLICT,
        ),
        (
            resolution_request(
                regions=(
                    region(
                        "footer",
                        LayoutRegionKind.FOOTER,
                        (10.0, 10.0, 90.0, 20.0),
                    ),
                    region(
                        "body",
                        LayoutRegionKind.TEXT,
                        (10.0, 30.0, 90.0, 50.0),
                    ),
                ),
                candidate_ids=("body", "footer"),
            ),
            LayoutReadingOrderReason.FOOTER_POSITION_CONFLICT,
        ),
    ),
)
def test_escalates_candidate_region_or_band_conflicts(
    case_request: LayoutReadingOrderRequest,
    expected_reason: LayoutReadingOrderReason,
) -> None:
    result = resolve(case_request)

    assert expected_reason in tuple(result.reasons)
    assert result.resolution is None


def test_escalates_ambiguous_native_block_lanes() -> None:
    request = resolution_request(
        regions=(
            region(
                "region",
                LayoutRegionKind.TEXT,
                (5.0, 5.0, 95.0, 95.0),
                block("left", (10.0, 10.0, 40.0, 20.0)),
                block("right", (60.0, 10.0, 90.0, 20.0)),
            ),
        ),
        candidate_ids=("region",),
        expected_block_ids=("left", "right"),
    )

    result = resolve(request)

    assert tuple(result.reasons) == (
        LayoutReadingOrderReason.NATIVE_BLOCK_ORDER_AMBIGUOUS,
    )


def test_result_rejects_forged_complete_permutation() -> None:
    request = resolution_request(
        regions=two_column_regions(),
        candidate_ids=(
            "left-top",
            "left-bottom",
            "right-top",
            "right-bottom",
        ),
        expected_block_ids=("block-left-top", "block-left-bottom"),
    )
    forged_resolution = LayoutReadingOrderResolution(
        region_order=LayoutReadingOrderRegionSequence(
            "right-top",
            "right-bottom",
            "left-top",
            "left-bottom",
        ),
        native_block_order=LayoutReadingOrderNativeBlockSequence(
            "block-left-top",
            "block-left-bottom",
        ),
    )

    with pytest.raises(ValueError, match="differs from derivation"):
        LayoutReadingOrderResult(
            request=request,
            status=LayoutReadingOrderStatus.RESOLVED,
            reasons=LayoutReadingOrderReasonInventory(),
            resolution=forged_resolution,
        )


def test_docling_candidate_flows_into_deterministic_verifier() -> None:
    regions = two_column_regions()
    configuration = DoclingReadingOrderConfiguration()
    render = LayoutReviewFixture().render_evidence()[2]
    docling_request = DoclingReadingOrderRequest(
        render_id=render.render_id,
        upstream_evidence_id="layout-gate:sha256:test",
        page_width_pixels=render.image_width,
        page_height_pixels=render.image_height,
        direction=LayoutReadingDirection.LEFT_TO_RIGHT,
        elements=LayoutReadingOrderCandidateElementInventory(
            *(
                LayoutReadingOrderCandidateElement(
                    region_id=item.region_id,
                    source_index=index,
                    kind=item.kind,
                    bounding_box_pixels=item.bounding_box_pixels,
                )
                for index, item in enumerate(regions)
            )
        ),
        configuration=configuration,
    )
    docling_result = DoclingReadingOrderActionizer(
        provider=InstalledDoclingReadingOrderProvider()
    ).action(request=docling_request)
    assert docling_result.candidate_evidence is not None
    request = LayoutReadingOrderRequest(
        render=render,
        upstream_evidence_id=docling_request.upstream_evidence_id,
        direction=LayoutReadingDirection.LEFT_TO_RIGHT,
        expected_blocks=LayoutReadingOrderExpectedBlockInventory(
            "block-left-top",
            "block-left-bottom",
        ),
        regions=LayoutReadingOrderRegionInventory(*regions),
        candidate_evidence=docling_result.candidate_evidence,
        configuration=LayoutReadingOrderConfiguration(),
    )

    result = resolve(request)

    assert result.status is LayoutReadingOrderStatus.RESOLVED


@pytest.mark.benchmark
@pytest.mark.parametrize(
    ("candidate_ids", "expected_identity"),
    (
        (
            ("left-top", "left-bottom", "right-top", "right-bottom"),
            "layout-reading-order-result:sha256:64ad725121df86d1264c914b475a942366e0c73a204b84867edfdcde52a28556",
        ),
        (
            ("left-top", "right-top", "left-bottom", "right-bottom"),
            "layout-reading-order-result:sha256:f13521aaec9421e6c9870bf3f92b68880c2357f2f07d4e0df34811237eeb9ccb",
        ),
    ),
)
def test_reading_order_result_identity_regression(
    candidate_ids: tuple[str, ...],
    expected_identity: str,
) -> None:
    request = resolution_request(
        regions=two_column_regions(),
        candidate_ids=candidate_ids,
        expected_block_ids=("block-left-top", "block-left-bottom"),
    )

    assert resolve(request).result_id == expected_identity

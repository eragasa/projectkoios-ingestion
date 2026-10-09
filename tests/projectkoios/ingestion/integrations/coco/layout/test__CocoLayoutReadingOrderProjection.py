"""Resolved-layout projection into COCO reading-order sidecar evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.ingestion.integrations.coco.layout.reading.order import (
    CocoLayoutAnnotationOrder,
    CocoLayoutImageReadingOrder,
    CocoLayoutNativeBlockOrder,
)
from projectkoios.ingestion.integrations.coco.layout.reading.projection.actionizer import (  # noqa: E501
    CocoLayoutReadingOrderProjectionActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.reading.projection.request import (  # noqa: E501
    CocoLayoutReadingOrderProjectionRequest,
)
from projectkoios.ingestion.integrations.coco.layout.reading.projection.result import (  # noqa: E501
    CocoLayoutReadingOrderProjectionResult,
)
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
)
from projectkoios.ingestion.layout.reading.order.region import (
    LayoutReadingOrderRegion,
    LayoutReadingOrderRegionInventory,
)
from projectkoios.ingestion.layout.reading.order.request import (
    LayoutReadingOrderRequest,
)
from projectkoios.ingestion.layout.reading.order.result import (
    LayoutReadingOrderResult,
)

from tests.projectkoios.ingestion.integrations.coco.layout.fixture import (
    coco_layout_bundle_fixture,
)
from tests.projectkoios.ingestion.layout.review.layout_review_support import (
    LayoutReviewFixture,
)


def resolved_layout_result() -> LayoutReadingOrderResult:
    bundle = coco_layout_bundle_fixture()
    render = LayoutReviewFixture().render_evidence()[2]
    detections = {
        detection.annotation_id: detection
        for detection in bundle.annotations.detections
    }
    regions = []
    proposal_by_annotation: dict[int, str] = {}
    for entry in bundle.lineage.entries:
        detection = detections[entry.annotation_id]
        proposal_by_annotation[entry.annotation_id] = entry.proposal_id
        category = bundle.annotations.profile.categories.require(
            detection.category_id
        )
        blocks = (
            (
                LayoutReadingOrderBlock(
                    block_id="native-block:001",
                    bounding_box_pixels=(30.0, 25.0, 40.0, 30.0),
                ),
            )
            if entry.annotation_id == 2
            else ()
        )
        regions.append(
            LayoutReadingOrderRegion(
                region_id=entry.proposal_id,
                kind=category.kind,
                bounding_box_pixels=detection.bounding_box_pixels,
                blocks=LayoutReadingOrderBlockInventory(*blocks),
            )
        )
    region_inventory = LayoutReadingOrderRegionInventory(*regions)
    direction = LayoutReadingDirection.LEFT_TO_RIGHT
    elements = LayoutReadingOrderCandidateElementInventory(
        *(
            LayoutReadingOrderCandidateElement(
                region_id=region.region_id,
                source_index=index,
                kind=region.kind,
                bounding_box_pixels=region.bounding_box_pixels,
            )
            for index, region in enumerate(region_inventory)
        )
    )
    candidate_evidence = LayoutReadingOrderCandidateEvidence(
        source_request_id="fixture-candidate-request:1",
        producer_implementation_id="fixture-candidate-producer:1",
        render_id=render.render_id,
        upstream_evidence_id=bundle.lineage.document_id,
        direction=direction,
        elements=elements,
        candidate=LayoutReadingOrderCandidate(
            proposal_by_annotation[2],
            proposal_by_annotation[1],
        ),
    )
    request = LayoutReadingOrderRequest(
        render=render,
        upstream_evidence_id=bundle.lineage.document_id,
        direction=direction,
        expected_blocks=LayoutReadingOrderExpectedBlockInventory(
            "native-block:001"
        ),
        regions=region_inventory,
        candidate_evidence=candidate_evidence,
        configuration=LayoutReadingOrderConfiguration(),
    )
    return DeterministicLayoutReadingOrderActionizer().action(request=request)


def projection_result() -> CocoLayoutReadingOrderProjectionResult:
    bundle = coco_layout_bundle_fixture()
    request = CocoLayoutReadingOrderProjectionRequest(
        annotations=bundle.annotations,
        lineage=bundle.lineage,
        layout_result=resolved_layout_result(),
        image_id=1,
    )
    return CocoLayoutReadingOrderProjectionActionizer().action(request=request)


def test_projects_complete_annotation_and_native_block_orders() -> None:
    result = projection_result()

    assert tuple(result.reading_order.annotation_order) == (2, 1)
    assert tuple(result.reading_order.native_block_order) == (
        "native-block:001",
    )


def test_projection_result_rejects_forged_order() -> None:
    result = projection_result()
    forged_order = CocoLayoutImageReadingOrder(
        image_id=1,
        annotation_order=CocoLayoutAnnotationOrder(1, 2),
        native_block_order=CocoLayoutNativeBlockOrder("native-block:001"),
    )

    with pytest.raises(ValueError, match="differs from derivation"):
        CocoLayoutReadingOrderProjectionResult(
            request=result.request,
            reading_order=forged_order,
        )


def test_projection_rejects_resolved_upstream_lineage_drift() -> None:
    bundle = coco_layout_bundle_fixture()
    exact = resolved_layout_result()
    drifted_request = replace(
        exact.request,
        upstream_evidence_id="coco-layout-lineage-document:sha256:drifted",
        candidate_evidence=replace(
            exact.request.candidate_evidence,
            upstream_evidence_id=(
                "coco-layout-lineage-document:sha256:drifted"
            ),
        ),
    )
    drifted_result = DeterministicLayoutReadingOrderActionizer().action(
        request=drifted_request
    )

    with pytest.raises(ValueError, match="upstream lineage differs"):
        CocoLayoutReadingOrderProjectionRequest(
            annotations=bundle.annotations,
            lineage=bundle.lineage,
            layout_result=drifted_result,
            image_id=1,
        )


def test_projection_rejects_lineage_profile_drift() -> None:
    bundle = coco_layout_bundle_fixture()
    drifted_lineage = replace(bundle.lineage, profile_id="profile:drifted")

    with pytest.raises(ValueError, match="profile differs"):
        CocoLayoutReadingOrderProjectionRequest(
            annotations=bundle.annotations,
            lineage=drifted_lineage,
            layout_result=resolved_layout_result(),
            image_id=1,
        )


@pytest.mark.benchmark
def test_projection_identity_regression() -> None:
    assert projection_result().result_id == (
        "coco-layout-reading-order-projection-result:sha256:997f57db6da31d8fb20e231a51a43234bda4fa9696c4b339c5860326e460322a"
    )

"""Pure strict derivation of COCO reading-order sidecar records."""

from __future__ import annotations

from projectkoios.ingestion.integrations.coco.layout.lineage import (
    CocoLayoutNativeBlockMembershipStatus,
)
from projectkoios.ingestion.integrations.coco.layout.reading.order import (
    CocoLayoutAnnotationOrder,
    CocoLayoutImageReadingOrder,
    CocoLayoutNativeBlockOrder,
)

from .request import CocoLayoutReadingOrderProjectionRequest


def derive_coco_layout_image_reading_order(
    *, request: CocoLayoutReadingOrderProjectionRequest
) -> CocoLayoutImageReadingOrder:
    """Map resolved proposal identities through exact annotation lineage."""
    if type(request) is not CocoLayoutReadingOrderProjectionRequest:
        raise TypeError(
            "request must be CocoLayoutReadingOrderProjectionRequest"
        )
    resolution = request.layout_result.resolution
    if resolution is None:
        raise RuntimeError("validated resolved layout lost its resolution")
    detections_by_id = {
        detection.annotation_id: detection
        for detection in request.annotations.detections
    }
    target_entries = tuple(
        entry
        for entry in request.lineage.entries
        if detections_by_id[entry.annotation_id].image_id == request.image_id
    )
    proposal_ids = tuple(entry.proposal_id for entry in target_entries)
    if len(proposal_ids) != len(set(proposal_ids)):
        raise ValueError(
            "COCO image lineage proposal identities must be unique"
        )
    entries_by_proposal = {entry.proposal_id: entry for entry in target_entries}
    resolved_region_ids = tuple(resolution.region_order)
    if set(resolved_region_ids) != set(proposal_ids):
        raise ValueError(
            "resolved regions must cover every COCO image annotation"
        )
    regions_by_id = {
        region.region_id: region
        for region in request.layout_result.request.regions
    }
    annotation_ids: list[int] = []
    lineage_block_ids: list[str] = []
    for region_id in resolved_region_ids:
        entry = entries_by_proposal[region_id]
        detection = detections_by_id[entry.annotation_id]
        region = regions_by_id[region_id]
        category = request.annotations.profile.categories.require(
            detection.category_id
        )
        if (
            region.kind is not category.kind
            or region.bounding_box_pixels != detection.bounding_box_pixels
        ):
            raise ValueError(
                "resolved region semantics differ from COCO annotation"
            )
        if (
            entry.native_block_membership_status
            is not CocoLayoutNativeBlockMembershipStatus.EVALUATED
        ):
            raise ValueError(
                "COCO reading order requires evaluated block membership"
            )
        region_block_ids = tuple(block.block_id for block in region.blocks)
        if set(region_block_ids) != set(entry.native_block_ids):
            raise ValueError(
                "resolved native-block membership differs from lineage"
            )
        annotation_ids.append(entry.annotation_id)
        lineage_block_ids.extend(entry.native_block_ids)
    if len(lineage_block_ids) != len(set(lineage_block_ids)):
        raise ValueError(
            "COCO native blocks must belong to exactly one annotation"
        )
    resolved_block_ids = tuple(resolution.native_block_order)
    if set(resolved_block_ids) != set(lineage_block_ids):
        raise ValueError(
            "resolved native blocks must cover evaluated COCO membership"
        )
    return CocoLayoutImageReadingOrder(
        image_id=request.image_id,
        annotation_order=CocoLayoutAnnotationOrder(*annotation_ids),
        native_block_order=CocoLayoutNativeBlockOrder(*resolved_block_ids),
    )

"""Pure conservative deterministic reading-order derivation."""

from __future__ import annotations

from collections import Counter

from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind

from .kind import (
    LayoutReadingDirection,
    LayoutReadingOrderReason,
    LayoutReadingOrderStatus,
)
from .reason import LayoutReadingOrderReasonInventory
from .region import LayoutReadingOrderRegion
from .request import LayoutReadingOrderRequest
from .resolution import (
    LayoutReadingOrderNativeBlockSequence,
    LayoutReadingOrderRegionSequence,
    LayoutReadingOrderResolution,
)

type LayoutReadingOrderDecision = tuple[
    LayoutReadingOrderStatus,
    LayoutReadingOrderReasonInventory,
    LayoutReadingOrderResolution | None,
]


def derive_layout_reading_order_decision(
    *, request: LayoutReadingOrderRequest
) -> LayoutReadingOrderDecision:
    """Derive one closed outcome from exact evidence and geometry."""
    if type(request) is not LayoutReadingOrderRequest:
        raise TypeError("request must be LayoutReadingOrderRequest")
    regions = tuple(request.regions)
    reasons = derive_layout_reading_order_input_reasons(request=request)
    region_order, geometry_reason = derive_layout_region_order(
        regions=regions,
        direction=request.direction,
    )
    if geometry_reason is not None:
        reasons.add(geometry_reason)
    native_block_ids: tuple[str, ...] | None = None
    if region_order is not None:
        native_block_ids, block_reason = derive_layout_native_block_order(
            regions=region_order,
            direction=request.direction,
        )
        if block_reason is not None:
            reasons.add(block_reason)
        expected_region_ids = tuple(region.region_id for region in region_order)
        if tuple(request.candidate_evidence.candidate) != expected_region_ids:
            reasons.add(
                LayoutReadingOrderReason.CANDIDATE_GEOMETRY_DISAGREEMENT
            )
    if reasons:
        return (
            LayoutReadingOrderStatus.ESCALATION_REQUIRED,
            LayoutReadingOrderReasonInventory(*sorted(reasons, key=str)),
            None,
        )
    if region_order is None or native_block_ids is None:
        raise RuntimeError("reading-order derivation lost complete evidence")
    return (
        LayoutReadingOrderStatus.RESOLVED,
        LayoutReadingOrderReasonInventory(),
        LayoutReadingOrderResolution(
            region_order=LayoutReadingOrderRegionSequence(
                *(region.region_id for region in region_order)
            ),
            native_block_order=LayoutReadingOrderNativeBlockSequence(
                *native_block_ids
            ),
        ),
    )


def derive_layout_reading_order_input_reasons(
    *, request: LayoutReadingOrderRequest
) -> set[LayoutReadingOrderReason]:
    """Find complete candidate, coverage, kind, and geometry failures."""
    reasons: set[LayoutReadingOrderReason] = set()
    regions = tuple(request.regions)
    region_ids = {region.region_id for region in regions}
    candidate_ids = tuple(request.candidate_evidence.candidate)
    if len(candidate_ids) != len(regions) or region_ids - set(candidate_ids):
        reasons.add(LayoutReadingOrderReason.CANDIDATE_INCOMPLETE)
    if set(candidate_ids) - region_ids:
        reasons.add(LayoutReadingOrderReason.CANDIDATE_UNKNOWN_REGION)
    expected_blocks = set(request.expected_blocks)
    assigned_ids = tuple(
        block.block_id for region in regions for block in region.blocks
    )
    assigned_counts = Counter(assigned_ids)
    assigned_blocks = set(assigned_ids)
    if expected_blocks - assigned_blocks:
        reasons.add(LayoutReadingOrderReason.UNASSIGNED_NATIVE_BLOCK)
    if assigned_blocks - expected_blocks:
        reasons.add(LayoutReadingOrderReason.UNKNOWN_NATIVE_BLOCK)
    if any(count > 1 for count in assigned_counts.values()):
        reasons.add(LayoutReadingOrderReason.DUPLICATE_NATIVE_BLOCK_ASSIGNMENT)
    if any(
        not layout_box_contains(
            outer=region.bounding_box_pixels,
            inner=block.bounding_box_pixels,
        )
        for region in regions
        for block in region.blocks
    ):
        reasons.add(LayoutReadingOrderReason.NATIVE_BLOCK_REGION_CONFLICT)
    unsupported = {LayoutRegionKind.SIDEBAR, LayoutRegionKind.OTHER}
    if any(region.kind in unsupported for region in regions):
        reasons.add(LayoutReadingOrderReason.UNSUPPORTED_REGION_KIND)
    if any(region.kind is LayoutRegionKind.CAPTION for region in regions):
        reasons.add(LayoutReadingOrderReason.CAPTION_ASSOCIATION_REQUIRED)
    if any(region.kind is LayoutRegionKind.FOOTNOTE for region in regions):
        reasons.add(LayoutReadingOrderReason.FOOTNOTE_ASSOCIATION_REQUIRED)
    if any(
        layout_boxes_overlap(lhs.bounding_box_pixels, rhs.bounding_box_pixels)
        for index, lhs in enumerate(regions)
        for rhs in regions[index + 1 :]
    ):
        reasons.add(LayoutReadingOrderReason.OVERLAPPING_REGIONS)
    headers = tuple(
        region for region in regions if region.kind is LayoutRegionKind.HEADER
    )
    nonheaders = tuple(
        region
        for region in regions
        if region.kind is not LayoutRegionKind.HEADER
    )
    if any(
        header.bounding_box_pixels[3] > other.bounding_box_pixels[1]
        for header in headers
        for other in nonheaders
    ):
        reasons.add(LayoutReadingOrderReason.HEADER_POSITION_CONFLICT)
    footers = tuple(
        region for region in regions if region.kind is LayoutRegionKind.FOOTER
    )
    nonfooters = tuple(
        region
        for region in regions
        if region.kind is not LayoutRegionKind.FOOTER
    )
    if any(
        footer.bounding_box_pixels[1] < other.bounding_box_pixels[3]
        for footer in footers
        for other in nonfooters
    ):
        reasons.add(LayoutReadingOrderReason.FOOTER_POSITION_CONFLICT)
    return reasons


def derive_layout_region_order(
    *,
    regions: tuple[LayoutReadingOrderRegion, ...],
    direction: LayoutReadingDirection,
) -> tuple[
    tuple[LayoutReadingOrderRegion, ...] | None,
    LayoutReadingOrderReason | None,
]:
    """Derive header, pure-column body, and footer order."""
    headers = tuple(
        region for region in regions if region.kind is LayoutRegionKind.HEADER
    )
    footers = tuple(
        region for region in regions if region.kind is LayoutRegionKind.FOOTER
    )
    body_candidates = tuple(
        region
        for region in regions
        if region.kind not in {LayoutRegionKind.HEADER, LayoutRegionKind.FOOTER}
    )
    leading_titles = derive_leading_spanning_titles(regions=body_candidates)
    leading_title_ids = {region.region_id for region in leading_titles}
    body = tuple(
        region
        for region in body_candidates
        if region.region_id not in leading_title_ids
    )
    header_order, reason = derive_layout_column_order(
        regions=headers,
        direction=direction,
    )
    if reason is not None:
        return None, reason
    leading_title_order, reason = derive_layout_column_order(
        regions=leading_titles,
        direction=direction,
    )
    if reason is not None:
        return None, reason
    body_order, reason = derive_layout_column_order(
        regions=body,
        direction=direction,
    )
    if reason is not None:
        return None, reason
    footer_order, reason = derive_layout_column_order(
        regions=footers,
        direction=direction,
    )
    if reason is not None:
        return None, reason
    return (
        *header_order,
        *leading_title_order,
        *body_order,
        *footer_order,
    ), None


def derive_leading_spanning_titles(
    *, regions: tuple[LayoutReadingOrderRegion, ...]
) -> tuple[LayoutReadingOrderRegion, ...]:
    """Find a consecutive title prefix spanning every remaining body region."""
    remaining = list(regions)
    leading: list[LayoutReadingOrderRegion] = []
    while len(remaining) > 1:
        first = min(
            remaining,
            key=lambda region: (
                region.bounding_box_pixels[1],
                region.bounding_box_pixels[0],
                region.region_id,
            ),
        )
        others = tuple(region for region in remaining if region is not first)
        content_left = min(
            region.bounding_box_pixels[0] for region in others
        )
        content_top = min(region.bounding_box_pixels[1] for region in others)
        content_right = max(
            region.bounding_box_pixels[2] for region in others
        )
        if not (
            first.kind is LayoutRegionKind.TITLE
            and first.bounding_box_pixels[3] <= content_top
            and first.bounding_box_pixels[0] <= content_left
            and first.bounding_box_pixels[2] >= content_right
        ):
            break
        leading.append(first)
        remaining.remove(first)
    return tuple(leading)


def derive_layout_column_order(
    *,
    regions: tuple[LayoutReadingOrderRegion, ...],
    direction: LayoutReadingDirection,
) -> tuple[
    tuple[LayoutReadingOrderRegion, ...],
    LayoutReadingOrderReason | None,
]:
    """Order pure disjoint columns and reject spanning or overlapping lanes."""
    if not regions:
        return (), None
    components = derive_horizontal_components(regions=regions)
    if any(
        not any(
            layout_boxes_overlap_vertically(
                lhs.bounding_box_pixels,
                rhs.bounding_box_pixels,
            )
            for lhs in left_component
            for rhs in right_component
        )
        for index, left_component in enumerate(components)
        for right_component in components[index + 1 :]
    ):
        return (), LayoutReadingOrderReason.COLUMN_ORDER_AMBIGUOUS
    ordered_columns: list[tuple[LayoutReadingOrderRegion, ...]] = []
    for component in components:
        left = max(region.bounding_box_pixels[0] for region in component)
        right = min(region.bounding_box_pixels[2] for region in component)
        if left >= right:
            return (), LayoutReadingOrderReason.SPANNING_REGION_AMBIGUOUS
        ordered = tuple(
            sorted(
                component,
                key=lambda region: (
                    region.bounding_box_pixels[1],
                    region.bounding_box_pixels[0],
                    region.region_id,
                ),
            )
        )
        if any(
            upper.bounding_box_pixels[3] > lower.bounding_box_pixels[1]
            for upper, lower in zip(ordered, ordered[1:], strict=False)
        ):
            return (), LayoutReadingOrderReason.COLUMN_ORDER_AMBIGUOUS
        ordered_columns.append(ordered)
    ordered_columns.sort(
        key=lambda column: min(
            region.bounding_box_pixels[0] for region in column
        ),
        reverse=direction is LayoutReadingDirection.RIGHT_TO_LEFT,
    )
    return tuple(
        region for column in ordered_columns for region in column
    ), None


def derive_horizontal_components(
    *, regions: tuple[LayoutReadingOrderRegion, ...]
) -> tuple[tuple[LayoutReadingOrderRegion, ...], ...]:
    """Partition regions by transitive positive horizontal overlap."""
    unvisited = set(range(len(regions)))
    components: list[tuple[LayoutReadingOrderRegion, ...]] = []
    while unvisited:
        pending = [min(unvisited)]
        indices: set[int] = set()
        while pending:
            index = pending.pop()
            if index in indices:
                continue
            indices.add(index)
            unvisited.discard(index)
            for other in tuple(unvisited):
                if layout_boxes_overlap_horizontally(
                    regions[index].bounding_box_pixels,
                    regions[other].bounding_box_pixels,
                ):
                    pending.append(other)
        components.append(tuple(regions[index] for index in sorted(indices)))
    return tuple(components)


def derive_layout_native_block_order(
    *,
    regions: tuple[LayoutReadingOrderRegion, ...],
    direction: LayoutReadingDirection,
) -> tuple[tuple[str, ...] | None, LayoutReadingOrderReason | None]:
    """Derive block order only for one mechanically coherent lane per region."""
    horizontal_sign = (
        1 if direction is LayoutReadingDirection.LEFT_TO_RIGHT else -1
    )
    ordered_ids: list[str] = []
    for region in regions:
        blocks = tuple(region.blocks)
        if len(blocks) > 1:
            left = max(block.bounding_box_pixels[0] for block in blocks)
            right = min(block.bounding_box_pixels[2] for block in blocks)
            if left >= right:
                return (
                    None,
                    LayoutReadingOrderReason.NATIVE_BLOCK_ORDER_AMBIGUOUS,
                )
        ordered = tuple(
            sorted(
                blocks,
                key=lambda block: (
                    block.bounding_box_pixels[1],
                    horizontal_sign * block.bounding_box_pixels[0],
                    block.block_id,
                ),
            )
        )
        if any(
            layout_boxes_overlap(
                upper.bounding_box_pixels,
                lower.bounding_box_pixels,
            )
            or upper.bounding_box_pixels[3] > lower.bounding_box_pixels[1]
            for upper, lower in zip(ordered, ordered[1:], strict=False)
        ):
            return (
                None,
                LayoutReadingOrderReason.NATIVE_BLOCK_ORDER_AMBIGUOUS,
            )
        ordered_ids.extend(block.block_id for block in ordered)
    return tuple(ordered_ids), None


def layout_box_contains(
    *,
    outer: tuple[float, float, float, float],
    inner: tuple[float, float, float, float],
) -> bool:
    """Return whether one box completely contains another."""
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def layout_boxes_overlap(
    lhs: tuple[float, float, float, float],
    rhs: tuple[float, float, float, float],
) -> bool:
    """Return whether two boxes have positive-area intersection."""
    return max(lhs[0], rhs[0]) < min(lhs[2], rhs[2]) and max(
        lhs[1], rhs[1]
    ) < min(lhs[3], rhs[3])


def layout_boxes_overlap_vertically(
    lhs: tuple[float, float, float, float],
    rhs: tuple[float, float, float, float],
) -> bool:
    """Return whether two boxes share positive vertical extent."""
    return max(lhs[1], rhs[1]) < min(lhs[3], rhs[3])


def layout_boxes_overlap_horizontally(
    lhs: tuple[float, float, float, float],
    rhs: tuple[float, float, float, float],
) -> bool:
    """Return whether two boxes share positive horizontal extent."""
    return max(lhs[0], rhs[0]) < min(lhs[2], rhs[2])

"""Cross-linked table contract and retained-resource validation."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum

from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedBlock,
    ExtractedDocument,
    IngestionWarning,
    Metadata,
    SourceSpan,
)
from projectkoios.ingestion.pdf.models import (
    RenderedRegion,
)
from projectkoios.ingestion.tables.contracts import (
    _MAX_ASSOCIATIONS_PER_CANDIDATE,
    _MAX_BACKEND_DRAWING_ITEMS_PER_PAGE,
    _MAX_BLOCKS_PER_REGION,
    _MAX_REGIONS_PER_CANDIDATE,
    _MAX_RULE_SEGMENTS_PER_PAGE,
    _MAX_TEXT_FIELD_CHARACTERS,
    _MAX_WARNINGS,
    TableAssociationRole,
    TableBoundaryKind,
    TableCandidate,
    TableDetectionConfiguration,
    TableDetectionInput,
    TableDetectionLimitError,
    TableDetectionResult,
    TableEvidenceStatus,
    TablePageRuleEvidence,
    TableRegionEvidence,
    TableRuleOrientation,
    TableRuleSegment,
    TableTextAssociation,
    _block_box,
    _bounded_string,
    _box_contains,
    _nonnegative_float,
    _nonnegative_integer,
    _point,
    _positive_float,
    _positive_integer,
    _union_boxes,
    _unique_strings,
    _unit_float,
    _validate_metadata,
    _validate_sha256,
    _validate_spans,
    _validated_box,
)
from projectkoios.ingestion.tables.detection import (
    _association_for_record,
    _BlockRecord,
    _boundary_from_rules,
    _cluster_rows,
    _cluster_values,
    _merged_records,
    _region_confidence,
    _source_label,
    _vertical_box_distance,
)


def _validate_input_parts(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    page_rules: tuple[TablePageRuleEvidence, ...],
    configuration: TableDetectionConfiguration,
) -> None:
    if not isinstance(document, ExtractedDocument):
        raise TypeError("document must be ExtractedDocument")
    if not isinstance(layouts, tuple) or not isinstance(page_rules, tuple):
        raise TypeError("table input collections must be immutable tuples")
    if not isinstance(configuration, TableDetectionConfiguration):
        raise TypeError("configuration must be TableDetectionConfiguration")
    if document.source.byte_length > configuration.max_source_bytes:
        raise TableDetectionLimitError("source exceeds max_source_bytes")
    if len(document.pages) > configuration.max_pages:
        raise TableDetectionLimitError("document pages exceed max_pages")
    if len(layouts) != len(document.pages) or len(page_rules) != len(
        document.pages
    ):
        raise ValueError("one layout and rule result is required per page")
    total_blocks = 0
    total_text_blocks = 0
    total_text = 0
    total_spans = 0
    total_rules = 0
    block_ids: set[str] = set()
    for page, layout, rules in zip(
        document.pages, layouts, page_rules, strict=True
    ):
        if not isinstance(layout, PageLayoutResult) or not isinstance(
            rules, TablePageRuleEvidence
        ):
            raise TypeError("table page evidence has an unsupported value")
        if (
            layout.source_id != document.source.source_id
            or layout.source_blob_id != document.source.blob_id
            or layout.source_content_hash != document.source.content_hash
            or layout.page_index != page.page_index
            or layout.page_width != page.width
            or layout.page_height != page.height
            or layout.rotation_degrees != page.rotation_degrees
            or layout.coordinate_system != page.coordinate_system
        ):
            raise ValueError("layout evidence does not match document page")
        expected_raw = tuple(
            (block.block_id, block.kind, block.source_spans)
            for block in page.blocks
        )
        actual_raw = tuple(
            (item.block_id, item.kind, item.source_spans)
            for item in layout.raw_blocks
        )
        if expected_raw != actual_raw:
            raise ValueError("layout raw blocks do not match document page")
        if (
            rules.source_id != document.source.source_id
            or rules.source_blob_id != document.source.blob_id
            or rules.source_content_hash != document.source.content_hash
            or rules.page_index != page.page_index
            or rules.page_width != page.width
            or rules.page_height != page.height
            or rules.rotation_degrees != page.rotation_degrees
            or rules.coordinate_system != page.coordinate_system
        ):
            raise ValueError("rule evidence does not match document page")
        total_rules += len(rules.segments)
        if (
            rules.ignored_drawing_item_count
            > configuration.max_backend_drawing_items_per_page
        ):
            raise TableDetectionLimitError(
                "ignored drawing items exceed their per-page limit"
            )
        if len(rules.segments) > configuration.max_rule_segments_per_page:
            raise TableDetectionLimitError(
                "rule segments exceed their per-page limit"
            )
        if total_rules > configuration.max_total_rule_segments:
            raise TableDetectionLimitError(
                "rule segments exceed their aggregate limit"
            )
        total_blocks += len(page.blocks)
        if total_blocks > configuration.max_input_blocks:
            raise TableDetectionLimitError(
                "input blocks exceed max_input_blocks"
            )
        for block in page.blocks:
            if block.block_id in block_ids:
                raise ValueError("document block IDs must be globally unique")
            block_ids.add(block.block_id)
            total_spans += len(block.source_spans)
            if total_spans > configuration.max_source_spans:
                raise TableDetectionLimitError(
                    "source spans exceed max_source_spans"
                )
            if block.kind == "text" and isinstance(block.text, str):
                total_text_blocks += 1
                total_text += len(block.text)
                if total_text_blocks > configuration.max_text_blocks:
                    raise TableDetectionLimitError(
                        "text blocks exceed max_text_blocks"
                    )
                if total_text > configuration.max_text_characters:
                    raise TableDetectionLimitError(
                        "text exceeds max_text_characters"
                    )


def _validate_result(result: TableDetectionResult) -> None:
    input_value = result.detection_input
    configuration = input_value.configuration
    if result.configuration_digest != configuration.configuration_digest:
        raise ValueError("result configuration digest is inconsistent")
    block_by_id = {
        block.block_id: block
        for page in input_value.document.pages
        for block in page.blocks
    }
    block_order = {
        block.block_id: (page.page_index, index)
        for page in input_value.document.pages
        for index, block in enumerate(page.blocks)
    }
    rules_by_id = {
        segment.segment_id: segment
        for page in input_value.page_rule_evidence
        for segment in page.segments
    }
    warning_by_id = {warning.warning_id: warning for warning in result.warnings}
    warning_ids = set(warning_by_id)
    candidate_ids: set[str] = set()
    previous_order: tuple[int, float] | None = None
    rendered: list[RenderedRegion] = []
    for candidate in result.candidates:
        if candidate.candidate_id in candidate_ids:
            raise ValueError("candidate IDs must be unique")
        candidate_ids.add(candidate.candidate_id)
        if candidate.detection_input_id != input_value.input_id:
            raise ValueError("candidate detection input is inconsistent")
        if candidate.configuration_digest != result.configuration_digest:
            raise ValueError("candidate configuration is inconsistent")
        if (
            candidate.processor_name != result.processor_name
            or candidate.processor_version != result.processor_version
        ):
            raise ValueError("candidate processor identity is inconsistent")
        if not set(candidate.warning_ids).issubset(warning_ids):
            raise ValueError("candidate references unknown warnings")
        expected_warning_ids = tuple(
            warning.warning_id
            for warning in result.warnings
            if candidate.candidate_id in warning.object_ids
        )
        if candidate.warning_ids != expected_warning_ids:
            raise ValueError("candidate warning links are incomplete")
        order = (
            candidate.regions[0].page_index,
            candidate.regions[0].source_bounding_box[1],
        )
        if previous_order is not None and order < previous_order:
            raise ValueError("table candidates are not in source order")
        previous_order = order
        expected_spans = tuple(
            span for region in candidate.regions for span in region.source_spans
        )
        if candidate.source_spans != expected_spans:
            raise ValueError("candidate source spans do not match regions")
        if candidate.source_label != _source_label(candidate.associations):
            raise ValueError("candidate source label is inconsistent")
        if any(
            association.block_id not in block_order
            for association in candidate.associations
        ):
            raise ValueError("table association references an unknown block")
        association_order = tuple(
            block_order[association.block_id]
            for association in candidate.associations
        )
        if association_order != tuple(sorted(association_order)):
            raise ValueError("table associations are not in source order")
        region_boundaries: list[TableBoundaryKind] = []
        for region in candidate.regions:
            if region.detection_input_id != input_value.input_id:
                raise ValueError("region detection input is inconsistent")
            if region.configuration_digest != result.configuration_digest:
                raise ValueError("region configuration is inconsistent")
            if (
                region.processor_name != result.processor_name
                or region.processor_version != result.processor_version
            ):
                raise ValueError("region processor identity is inconsistent")
            blocks: list[ExtractedBlock] = []
            for block_id in region.block_ids:
                block = block_by_id.get(block_id)
                if block is None:
                    raise ValueError(
                        "region references an unknown source block"
                    )
                blocks.append(block)
            expected_region_spans = tuple(
                span for block in blocks for span in block.source_spans
            )
            if region.source_spans != expected_region_spans:
                raise ValueError("region source spans do not match blocks")
            rules: list[TableRuleSegment] = []
            for segment_id in region.rule_segment_ids:
                segment = rules_by_id.get(segment_id)
                if segment is None:
                    raise ValueError(
                        "region references an unknown rule segment"
                    )
                if segment.page_index != region.page_index:
                    raise ValueError("region rule segment page is inconsistent")
                rules.append(segment)
            block_boxes = tuple(
                box
                for block in blocks
                if (box := _block_box(block.source_spans)) is not None
            )
            if len(block_boxes) != len(blocks):
                raise ValueError("table region block geometry is incomplete")
            expected_box = _union_boxes(
                block_boxes + tuple(rule.bounding_box for rule in rules)
            )
            if region.source_bounding_box != expected_box:
                raise ValueError("table region bounding box is inconsistent")
            records = tuple(
                _BlockRecord(
                    block=block,
                    page_index=region.page_index,
                    box=box,
                    order=index,
                    layout_confidence=1.0,
                )
                for index, (block, box) in enumerate(
                    zip(blocks, block_boxes, strict=True)
                )
            )
            rows = _cluster_rows(
                records, configuration.row_alignment_tolerance_points
            )
            qualifying_rows = tuple(
                row for row in rows if len(row) >= configuration.minimum_columns
            )
            anchors = _cluster_values(
                tuple(
                    record.box[0] for row in qualifying_rows for record in row
                ),
                configuration.column_alignment_tolerance_points,
            )
            if (
                len(rows) != region.row_band_count
                or len(anchors) != region.column_band_count
            ):
                raise ValueError(
                    "table region row/column evidence is inconsistent"
                )
            base_records = tuple(
                record for row in qualifying_rows for record in row
            )
            expected_merged = _merged_records(
                rows,
                base_records,
                _union_boxes(tuple(record.box for record in base_records)),
                anchors,
                configuration,
            )
            if region.merged_cell_signal_block_ids != tuple(
                record.block.block_id for record in expected_merged
            ):
                raise ValueError("merged-cell signal evidence is inconsistent")
            boundary = _boundary_from_rules(tuple(rules))
            region_boundaries.append(boundary)
            has_title = any(
                association.page_index == region.page_index
                and association.role
                in (
                    TableAssociationRole.TITLE,
                    TableAssociationRole.CONTINUATION_LABEL,
                )
                for association in candidate.associations
            )
            prose_like = any(
                len(block.text or "") > configuration.prose_character_threshold
                for block in blocks
            )
            expected_confidence = _region_confidence(
                boundary,
                has_title=has_title,
                prose_like=prose_like,
            )
            if region.confidence != expected_confidence:
                raise ValueError("table region confidence is inconsistent")
            horizontal = sum(
                rule.orientation is TableRuleOrientation.HORIZONTAL
                for rule in rules
            )
            vertical = sum(
                rule.orientation is TableRuleOrientation.VERTICAL
                for rule in rules
            )
            expected_evidence: Metadata = (
                ("row_band_count", str(region.row_band_count)),
                ("column_band_count", str(region.column_band_count)),
                ("horizontal_rule_count", str(horizontal)),
                ("vertical_rule_count", str(vertical)),
                (
                    "merged_cell_signal_count",
                    str(len(region.merged_cell_signal_block_ids)),
                ),
                ("title_or_continuation_present", str(has_title).lower()),
                ("prose_like", str(prose_like).lower()),
            )
            if region.evidence != expected_evidence:
                raise ValueError("table region evidence is inconsistent")
            _validate_region_against_input(region, input_value)
            rendered.append(region.rendered_region)
        expected_boundary = (
            region_boundaries[0]
            if len(set(region_boundaries)) == 1
            else TableBoundaryKind.MIXED
        )
        if candidate.boundary_kind is not expected_boundary:
            raise ValueError("candidate boundary kind is inconsistent")
        expected_confidence = min(
            region.confidence for region in candidate.regions
        )
        if candidate.confidence != expected_confidence:
            raise ValueError("candidate confidence is inconsistent")
        expected_status = (
            TableEvidenceStatus.PROPOSED
            if candidate.confidence
            >= configuration.proposed_confidence_threshold
            else TableEvidenceStatus.AMBIGUOUS
        )
        if candidate.evidence_status is not expected_status:
            raise ValueError("candidate evidence status is inconsistent")
        expected_candidate_evidence: Metadata = (
            ("page_region_count", str(len(candidate.regions))),
            ("first_page_index", str(candidate.regions[0].page_index)),
            ("last_page_index", str(candidate.regions[-1].page_index)),
            ("explicit_continuation", str(len(candidate.regions) > 1).lower()),
        )
        if candidate.evidence != expected_candidate_evidence:
            raise ValueError("candidate evidence is inconsistent")
        expected_warning_codes: list[str] = []
        for region, boundary in zip(
            candidate.regions, region_boundaries, strict=True
        ):
            if region.confidence < configuration.proposed_confidence_threshold:
                expected_warning_codes.append("table.ambiguous_candidate")
            if dict(region.evidence)["prose_like"] == "true":
                expected_warning_codes.append("table.prose_like_candidate")
            if region.merged_cell_signal_block_ids:
                expected_warning_codes.append("table.merged_cell_signal")
            if boundary is TableBoundaryKind.MIXED:
                expected_warning_codes.append("table.mixed_boundary_evidence")
        if len(set(region_boundaries)) > 1:
            expected_warning_codes.append("table.mixed_boundary_evidence")
        expected_warning_codes = list(dict.fromkeys(expected_warning_codes))
        actual_warning_codes = [
            warning_by_id[warning_id].code
            for warning_id in candidate.warning_ids
        ]
        if actual_warning_codes != expected_warning_codes:
            raise ValueError("candidate warning evidence is inconsistent")
        for association in candidate.associations:
            block = block_by_id.get(association.block_id)
            if block is None or block.text != association.text:
                raise ValueError(
                    "table association does not match source block"
                )
            if block.source_spans != association.source_spans:
                raise ValueError("table association spans are inconsistent")
            box = _block_box(block.source_spans)
            if box is None:
                raise ValueError("table association geometry is incomplete")
            expected_association = _association_for_record(
                _BlockRecord(
                    block=block,
                    page_index=association.page_index,
                    box=box,
                    order=0,
                    layout_confidence=1.0,
                )
            )
            if association != expected_association:
                raise ValueError("table association evidence is inconsistent")
            if not any(
                region.page_index == association.page_index
                and not (
                    box[2] < region.source_bounding_box[0]
                    or box[0] > region.source_bounding_box[2]
                )
                and _vertical_box_distance(box, region.source_bounding_box)
                <= configuration.association_distance_points
                for region in candidate.regions
            ):
                raise ValueError("table association is not near its candidate")
    _validate_rendered_aggregate(tuple(rendered), configuration)
    for warning in result.warnings:
        if not set(warning.object_ids).intersection(candidate_ids):
            raise ValueError("table warning is not linked to a candidate")
    _validate_retained_size(result, configuration.max_result_bytes)


def _validate_region_against_input(
    region: TableRegionEvidence, detection_input: TableDetectionInput
) -> None:
    document = detection_input.document
    page = next(
        item for item in document.pages if item.page_index == region.page_index
    )
    rendered = region.rendered_region
    if (
        rendered.source_id != document.source.source_id
        or rendered.source_blob_id != document.source.blob_id
        or rendered.source_content_hash != document.source.content_hash
        or rendered.page_index != region.page_index
        or rendered.page_rotation_degrees != page.rotation_degrees
        or rendered.coordinate_system != page.coordinate_system
        or not _box_contains(
            rendered.source_bounding_box, region.source_bounding_box
        )
    ):
        raise ValueError("rendered region does not match table source evidence")


def _preflight_result(
    detection_input: TableDetectionInput,
    candidates: tuple[TableCandidate, ...],
    warnings: tuple[IngestionWarning, ...],
    processor_name: str,
    processor_version: str,
) -> None:
    if not isinstance(detection_input, TableDetectionInput):
        raise TypeError("detection_input must be TableDetectionInput")
    if not isinstance(candidates, tuple) or not isinstance(warnings, tuple):
        raise TypeError("table result collections must be immutable tuples")
    configuration = detection_input.configuration
    if len(candidates) > configuration.max_candidates:
        raise TableDetectionLimitError("candidates exceed max_candidates")
    if len(warnings) > configuration.max_warnings:
        raise TableDetectionLimitError("warnings exceed max_warnings")
    if any(not isinstance(item, TableCandidate) for item in candidates):
        raise TypeError("candidates contain an unsupported value")
    if any(not isinstance(item, IngestionWarning) for item in warnings):
        raise TypeError("warnings contain an unsupported value")
    _bounded_string("processor name", processor_name, nonempty=True)
    _bounded_string("processor version", processor_version, nonempty=True)


def _validate_rendered_aggregate(
    regions: tuple[RenderedRegion, ...],
    configuration: TableDetectionConfiguration,
) -> None:
    if any(not isinstance(region, RenderedRegion) for region in regions):
        raise TypeError("renderer returned an unsupported region value")
    unique = {region.region_id: region for region in regions}
    if sum(region.byte_length for region in unique.values()) > (
        configuration.max_total_rendered_png_bytes
    ):
        raise TableDetectionLimitError(
            "rendered PNG bytes exceed max_total_rendered_png_bytes"
        )
    if (
        sum(
            region.width_pixels * region.height_pixels
            for region in unique.values()
        )
        > configuration.max_total_rendered_pixels
    ):
        raise TableDetectionLimitError(
            "rendered pixels exceed max_total_rendered_pixels"
        )


def _validate_rule_parts(
    source_id: str,
    source_blob_id: str,
    page_index: int,
    orientation: TableRuleOrientation,
    start: tuple[float, float],
    end: tuple[float, float],
    stroke_width: float,
    source_object_id: str,
) -> tuple[tuple[float, float], tuple[float, float], float]:
    _bounded_string("rule source ID", source_id, nonempty=True)
    _bounded_string("rule source blob ID", source_blob_id, nonempty=True)
    _nonnegative_integer("rule page index", page_index)
    if not isinstance(orientation, TableRuleOrientation):
        raise TypeError("rule orientation is unsupported")
    normalized_start = _point("rule start", start)
    normalized_end = _point("rule end", end)
    if normalized_start == normalized_end:
        raise ValueError("rule segment must have positive length")
    if orientation is TableRuleOrientation.HORIZONTAL:
        if normalized_start[1] != normalized_end[1]:
            raise ValueError("horizontal rule endpoints are inconsistent")
    elif normalized_start[0] != normalized_end[0]:
        raise ValueError("vertical rule endpoints are inconsistent")
    width = _nonnegative_float("rule stroke width", stroke_width)
    _bounded_string("rule source object ID", source_object_id, nonempty=True)
    return normalized_start, normalized_end, width


def _validate_page_rules(
    source_id: str,
    source_blob_id: str,
    source_content_hash: str,
    page_index: int,
    page_width: float,
    page_height: float,
    rotation_degrees: int,
    segments: tuple[TableRuleSegment, ...],
    ignored_drawing_item_count: int,
    processor_name: str,
    processor_version: str,
    backend_name: str,
    backend_version: str,
) -> None:
    for name, value in (
        ("rule source ID", source_id),
        ("rule source blob ID", source_blob_id),
        ("rule processor name", processor_name),
        ("rule processor version", processor_version),
        ("rule backend name", backend_name),
        ("rule backend version", backend_version),
    ):
        _bounded_string(name, value, nonempty=True)
    _validate_sha256("rule source hash", source_content_hash)
    if source_blob_id != f"blob:sha256:{source_content_hash}":
        raise ValueError("rule source blob and hash are inconsistent")
    _nonnegative_integer("rule page index", page_index)
    width = _positive_float("rule page width", page_width)
    height = _positive_float("rule page height", page_height)
    if rotation_degrees not in (0, 90, 180, 270):
        raise ValueError("rule page rotation is unsupported")
    if not isinstance(segments, tuple):
        raise TypeError("rule segments must be an immutable tuple")
    if len(segments) > _MAX_RULE_SEGMENTS_PER_PAGE:
        raise TableDetectionLimitError(
            "rule segments exceed their hard per-page limit"
        )
    _nonnegative_integer(
        "ignored drawing item count", ignored_drawing_item_count
    )
    if ignored_drawing_item_count > _MAX_BACKEND_DRAWING_ITEMS_PER_PAGE:
        raise TableDetectionLimitError(
            "ignored drawing items exceed their hard limit"
        )
    segment_ids: set[str] = set()
    for segment in segments:
        if not isinstance(segment, TableRuleSegment):
            raise TypeError("rule segments contain an unsupported value")
        if (
            segment.source_id != source_id
            or segment.source_blob_id != source_blob_id
            or segment.page_index != page_index
        ):
            raise ValueError("rule segment source is inconsistent")
        if segment.segment_id in segment_ids:
            raise ValueError("rule segment IDs must be unique")
        segment_ids.add(segment.segment_id)
        if any(
            coordinate < 0.0
            for point in (segment.start, segment.end)
            for coordinate in point
        ) or any(
            point[0] > width or point[1] > height
            for point in (segment.start, segment.end)
        ):
            raise ValueError("rule segment is outside its source page")


def _validate_association_parts(
    role: TableAssociationRole,
    page_index: int,
    block_id: str,
    text: str | None,
    source_spans: tuple[SourceSpan, ...],
    confidence: float,
    evidence: Metadata,
) -> float:
    if not isinstance(role, TableAssociationRole):
        raise TypeError("table association role is unsupported")
    _nonnegative_integer("association page index", page_index)
    _bounded_string("association block ID", block_id, nonempty=True)
    _bounded_string(
        "association text",
        text,
        nonempty=True,
        limit=_MAX_TEXT_FIELD_CHARACTERS,
    )
    _validate_spans(source_spans)
    if any(span.page_index != page_index for span in source_spans):
        raise ValueError("association spans do not match its page")
    _validate_metadata(evidence)
    return _unit_float("association confidence", confidence)


def _validate_region_parts(
    detection_input_id: str,
    page_index: int,
    source_bounding_box: BoundingBox,
    block_ids: tuple[str, ...],
    source_spans: tuple[SourceSpan, ...],
    row_band_count: int,
    column_band_count: int,
    rule_segment_ids: tuple[str, ...],
    merged_cell_signal_block_ids: tuple[str, ...],
    rendered_region: RenderedRegion,
    confidence: float,
    evidence: Metadata,
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> tuple[BoundingBox, float]:
    _bounded_string("detection input ID", detection_input_id, nonempty=True)
    _nonnegative_integer("table region page index", page_index)
    box = _validated_box(source_bounding_box)
    _unique_strings("table region block IDs", block_ids, required=True)
    if len(block_ids) > _MAX_BLOCKS_PER_REGION:
        raise TableDetectionLimitError(
            "table region block IDs exceed their hard limit"
        )
    _validate_spans(source_spans)
    _positive_integer("row band count", row_band_count)
    _positive_integer("column band count", column_band_count)
    _unique_strings("rule segment IDs", rule_segment_ids)
    if len(rule_segment_ids) > _MAX_RULE_SEGMENTS_PER_PAGE:
        raise TableDetectionLimitError(
            "rule segment IDs exceed their hard limit"
        )
    _unique_strings(
        "merged-cell signal block IDs", merged_cell_signal_block_ids
    )
    if not set(merged_cell_signal_block_ids).issubset(set(block_ids)):
        raise ValueError("merged-cell signals must reference region blocks")
    if not isinstance(rendered_region, RenderedRegion):
        raise TypeError("rendered_region must be RenderedRegion")
    if rendered_region.page_index != page_index:
        raise ValueError("rendered region page does not match table region")
    if not _box_contains(rendered_region.source_bounding_box, box):
        raise ValueError("rendered source box does not contain table region")
    _validate_metadata(evidence)
    for name, value in (
        ("region processor name", processor_name),
        ("region processor version", processor_version),
        ("region configuration digest", configuration_digest),
    ):
        _bounded_string(name, value, nonempty=True)
    return box, _unit_float("table region confidence", confidence)


def _validate_candidate_parts(
    detection_input_id: str,
    boundary_kind: TableBoundaryKind,
    evidence_status: TableEvidenceStatus,
    source_label: str | None,
    regions: tuple[TableRegionEvidence, ...],
    associations: tuple[TableTextAssociation, ...],
    source_spans: tuple[SourceSpan, ...],
    confidence: float,
    evidence: Metadata,
    warning_ids: tuple[str, ...],
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> float:
    _bounded_string(
        "candidate detection input ID", detection_input_id, nonempty=True
    )
    if not isinstance(boundary_kind, TableBoundaryKind):
        raise TypeError("table boundary kind is unsupported")
    if not isinstance(evidence_status, TableEvidenceStatus):
        raise TypeError("table evidence status is unsupported")
    if source_label is not None:
        _bounded_string("table source label", source_label, nonempty=True)
    if not isinstance(regions, tuple) or not regions:
        raise ValueError("table candidate requires immutable regions")
    if any(not isinstance(region, TableRegionEvidence) for region in regions):
        raise TypeError("table regions contain an unsupported value")
    if len(regions) > _MAX_REGIONS_PER_CANDIDATE:
        raise TableDetectionLimitError("too many table regions")
    pages = tuple(region.page_index for region in regions)
    if pages != tuple(sorted(set(pages))):
        raise ValueError("table regions must occupy unique ordered pages")
    if any(
        region.detection_input_id != detection_input_id for region in regions
    ):
        raise ValueError("table region detection input is inconsistent")
    if not isinstance(associations, tuple):
        raise TypeError("table associations must be an immutable tuple")
    if any(
        not isinstance(association, TableTextAssociation)
        for association in associations
    ):
        raise TypeError("table associations contain an unsupported value")
    if len(associations) > _MAX_ASSOCIATIONS_PER_CANDIDATE:
        raise TableDetectionLimitError(
            "table associations exceed their hard limit"
        )
    association_ids = tuple(item.association_id for item in associations)
    if len(set(association_ids)) != len(association_ids):
        raise ValueError("table association IDs must be unique")
    if tuple(
        (association.page_index, association.block_id)
        for association in associations
    ) != tuple(
        sorted(
            (association.page_index, association.block_id)
            for association in associations
        )
    ):
        # Extractor block IDs include stable physical order but lexical sorting
        # is not the semantic ordering rule, so only require page order here.
        if tuple(item.page_index for item in associations) != tuple(
            sorted(item.page_index for item in associations)
        ):
            raise ValueError("table associations must be in page order")
    _validate_spans(source_spans)
    _validate_metadata(evidence)
    _unique_strings("table candidate warning IDs", warning_ids)
    if len(warning_ids) > _MAX_WARNINGS:
        raise TableDetectionLimitError(
            "table candidate warning IDs exceed their hard limit"
        )
    for name, value in (
        ("candidate processor name", processor_name),
        ("candidate processor version", processor_version),
        ("candidate configuration digest", configuration_digest),
    ):
        _bounded_string(name, value, nonempty=True)
    return _unit_float("table candidate confidence", confidence)


def _validate_retained_size(value: object, limit: int) -> None:
    total = 0
    stack = [value]
    seen: set[int] = set()
    while stack:
        item = stack.pop()
        if item is None or isinstance(item, (bool, int, float, Enum)):
            total += 16
        elif isinstance(item, str):
            total += len(item.encode("utf-8")) + 8
        elif isinstance(item, bytes):
            total += len(item)
        elif isinstance(item, tuple):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            total += 8 * len(item)
            stack.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            for field in fields(item):
                total += len(field.name) + 3
                if isinstance(item, RenderedRegion) and field.name == "content":
                    continue
                stack.append(getattr(item, field.name))
        else:
            raise TypeError("table result contains unsupported evidence")
        if total > limit:
            raise TableDetectionLimitError(
                "table result exceeds max_result_bytes"
            )

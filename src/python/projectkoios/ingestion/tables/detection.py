"""Deterministic table candidate planning and materialization."""

from __future__ import annotations

from dataclasses import dataclass, replace
from io import BytesIO
from typing import BinaryIO, Protocol

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedBlock,
    ExtractedDocument,
    IngestionWarning,
    Metadata,
    WarningSeverity,
)
from projectkoios.ingestion.pdf.models import (
    PageRegionSelection,
    RenderedRegion,
)
from projectkoios.ingestion.pdf.renderer import PageRegionRenderer
from projectkoios.ingestion.tables.contracts import (
    _CAPTION,
    _CONTINUED,
    _NOTE,
    _TABLE_TITLE,
    TableAssociationRole,
    TableBoundaryKind,
    TableCandidate,
    TableDetectionConfiguration,
    TableDetectionInput,
    TableDetectionLimitError,
    TableDetectionResult,
    TableEvidenceStatus,
    TableRegionEvidence,
    TableRuleInspector,
    TableRuleOrientation,
    TableRuleSegment,
    TableTextAssociation,
    _block_box,
    _boxes_intersect,
    _expand_box,
    _padded_box,
    _union_boxes,
    _validate_rendered_aggregate,
)
from projectkoios.ingestion.tables.inspection import _read_exact_payload


class _DetectorContext(Protocol):
    name: str
    version: str
    configuration: TableDetectionConfiguration
    region_renderer: PageRegionRenderer
    rule_inspector: TableRuleInspector

    @property
    def configuration_digest(self) -> str: ...


@dataclass(frozen=True)
class _BlockRecord:
    block: ExtractedBlock
    page_index: int
    box: BoundingBox
    order: int
    layout_confidence: float

    @property
    def center_y(self) -> float:
        return (self.box[1] + self.box[3]) / 2.0


@dataclass(frozen=True)
class _ProvisionalRegion:
    page_index: int
    box: BoundingBox
    blocks: tuple[_BlockRecord, ...]
    row_count: int
    column_count: int
    column_anchors: tuple[float, ...]
    rules: tuple[TableRuleSegment, ...]
    merged_block_ids: tuple[str, ...]
    associations: tuple[TableTextAssociation, ...]
    source_label: str | None
    boundary_kind: TableBoundaryKind
    confidence: float
    evidence_status: TableEvidenceStatus
    evidence: Metadata
    warning_codes: tuple[str, ...]
    selection: PageRegionSelection


@dataclass(frozen=True)
class _ProvisionalCandidate:
    key: str
    regions: tuple[_ProvisionalRegion, ...]
    associations: tuple[TableTextAssociation, ...]
    source_label: str | None
    boundary_kind: TableBoundaryKind
    confidence: float
    evidence_status: TableEvidenceStatus
    evidence: Metadata
    warning_codes: tuple[str, ...]


class _DeterministicTableCandidateDetector:
    def detect_with_layout(
        self: _DetectorContext,
        document: ExtractedDocument,
        content: BinaryIO,
        layouts: tuple[PageLayoutResult, ...],
    ) -> TableDetectionResult:
        payload = _read_exact_payload(
            document.source, content, self.configuration
        )
        page_rules = self.rule_inspector.inspect(
            document,
            BytesIO(payload),
            self.configuration,
        )
        detection_input = TableDetectionInput.create(
            document=document,
            layouts=layouts,
            page_rule_evidence=page_rules,
            configuration=self.configuration,
        )
        page_regions = _detect_page_regions(detection_input)
        provisional = _link_page_regions(page_regions, self.configuration)
        if len(provisional) > self.configuration.max_candidates:
            raise TableDetectionLimitError(
                "table candidates exceed max_candidates"
            )
        if sum(len(item.warning_codes) for item in provisional) > (
            self.configuration.max_warnings
        ):
            raise TableDetectionLimitError("warnings exceed max_warnings")
        selections = tuple(
            region.selection
            for candidate in provisional
            for region in candidate.regions
        )
        rendered_by_selection: dict[PageRegionSelection, RenderedRegion] = {}
        if selections:
            rendered = self.region_renderer.render(
                document.source,
                BytesIO(payload),
                selections,
            )
            for selection, region in zip(selections, rendered, strict=True):
                previous = rendered_by_selection.get(selection)
                if previous is not None and previous != region:
                    raise ValueError(
                        "renderer returned inconsistent duplicate selections"
                    )
                rendered_by_selection[selection] = region
            _validate_rendered_aggregate(
                tuple(rendered_by_selection.values()), self.configuration
            )
        base_candidates: list[TableCandidate] = []
        candidate_provisional: list[_ProvisionalCandidate] = []
        for item in provisional:
            regions = tuple(
                TableRegionEvidence.create(
                    detection_input_id=detection_input.input_id,
                    page_index=region.page_index,
                    source_bounding_box=region.box,
                    block_ids=tuple(
                        block.block.block_id for block in region.blocks
                    ),
                    source_spans=tuple(
                        span
                        for block in region.blocks
                        for span in block.block.source_spans
                    ),
                    row_band_count=region.row_count,
                    column_band_count=region.column_count,
                    rule_segment_ids=tuple(
                        rule.segment_id for rule in region.rules
                    ),
                    merged_cell_signal_block_ids=region.merged_block_ids,
                    rendered_region=rendered_by_selection[region.selection],
                    confidence=region.confidence,
                    evidence=region.evidence,
                    processor_name=self.name,
                    processor_version=self.version,
                    configuration_digest=self.configuration_digest,
                )
                for region in item.regions
            )
            source_spans = tuple(
                span for region in regions for span in region.source_spans
            )
            candidate = TableCandidate.create(
                detection_input_id=detection_input.input_id,
                boundary_kind=item.boundary_kind,
                evidence_status=item.evidence_status,
                source_label=item.source_label,
                regions=regions,
                associations=item.associations,
                source_spans=source_spans,
                confidence=item.confidence,
                evidence=item.evidence,
                warning_ids=(),
                processor_name=self.name,
                processor_version=self.version,
                configuration_digest=self.configuration_digest,
            )
            base_candidates.append(candidate)
            candidate_provisional.append(item)
        warnings = _materialize_warnings(
            tuple(base_candidates), tuple(candidate_provisional)
        )
        warning_ids_by_candidate: dict[str, list[str]] = {}
        candidate_ids = {
            candidate.candidate_id for candidate in base_candidates
        }
        for warning in warnings:
            for object_id in warning.object_ids:
                if object_id in candidate_ids:
                    warning_ids_by_candidate.setdefault(object_id, []).append(
                        warning.warning_id
                    )
        candidates = tuple(
            replace(
                candidate,
                warning_ids=tuple(
                    warning_ids_by_candidate.get(candidate.candidate_id, ())
                ),
            )
            for candidate in base_candidates
        )
        return TableDetectionResult.create(
            detection_input=detection_input,
            candidates=candidates,
            warnings=warnings,
            processor_name=self.name,
            processor_version=self.version,
        )


def _detect_page_regions(
    detection_input: TableDetectionInput,
) -> tuple[_ProvisionalRegion, ...]:
    configuration = detection_input.configuration
    results: list[_ProvisionalRegion] = []
    rules_by_page = {
        item.page_index: item.segments
        for item in detection_input.page_rule_evidence
    }
    for page, layout in zip(
        detection_input.document.pages,
        detection_input.layouts,
        strict=True,
    ):
        records = _page_records(page.blocks, layout)
        associations_by_id = {
            record.block.block_id: association
            for record in records
            if (association := _association_for_record(record)) is not None
        }
        data_records = tuple(
            record
            for record in records
            if record.block.block_id not in associations_by_id
        )
        rows = _cluster_rows(
            data_records, configuration.row_alignment_tolerance_points
        )
        qualifying = tuple(
            row for row in rows if len(row) >= configuration.minimum_columns
        )
        for row_group in _group_qualifying_rows(
            qualifying, configuration.maximum_row_gap_points
        ):
            if len(row_group) < configuration.minimum_rows:
                continue
            base = tuple(record for row in row_group for record in row)
            anchors = _cluster_values(
                tuple(record.box[0] for record in base),
                configuration.column_alignment_tolerance_points,
            )
            if len(anchors) < configuration.minimum_columns:
                continue
            if not _rows_support_columns(
                row_group,
                anchors,
                configuration.column_alignment_tolerance_points,
                configuration.minimum_columns,
            ):
                continue
            base_box = _union_boxes(tuple(record.box for record in base))
            merged = _merged_records(
                rows,
                base,
                base_box,
                anchors,
                configuration,
            )
            blocks = tuple(
                sorted(
                    {*base, *merged},
                    key=lambda item: item.order,
                )
            )
            if len(blocks) > configuration.max_blocks_per_region:
                raise TableDetectionLimitError(
                    "table blocks exceed max_blocks_per_region"
                )
            block_box = _union_boxes(tuple(record.box for record in blocks))
            rules = _nearby_rules(
                block_box,
                rules_by_page[page.page_index],
                configuration.rule_proximity_points,
            )
            region_box = _union_boxes(
                (block_box, *(rule.bounding_box for rule in rules))
            )
            association_values = _nearby_associations(
                region_box,
                records,
                associations_by_id,
                configuration.association_distance_points,
            )
            if len(association_values) > (
                configuration.max_associations_per_candidate
            ):
                raise TableDetectionLimitError(
                    "table associations exceed their configured limit"
                )
            label = _source_label(association_values)
            horizontal = sum(
                rule.orientation is TableRuleOrientation.HORIZONTAL
                for rule in rules
            )
            vertical = sum(
                rule.orientation is TableRuleOrientation.VERTICAL
                for rule in rules
            )
            boundary = _boundary_from_rules(rules)
            prose_like = any(
                len(record.block.text or "")
                > configuration.prose_character_threshold
                for record in blocks
            )
            has_title = any(
                association.role
                in (
                    TableAssociationRole.TITLE,
                    TableAssociationRole.CONTINUATION_LABEL,
                )
                for association in association_values
            )
            confidence = _region_confidence(
                boundary, has_title=has_title, prose_like=prose_like
            )
            status = (
                TableEvidenceStatus.PROPOSED
                if confidence >= configuration.proposed_confidence_threshold
                else TableEvidenceStatus.AMBIGUOUS
            )
            warning_codes: list[str] = []
            if status is TableEvidenceStatus.AMBIGUOUS:
                warning_codes.append("table.ambiguous_candidate")
            if prose_like:
                warning_codes.append("table.prose_like_candidate")
            if merged:
                warning_codes.append("table.merged_cell_signal")
            if boundary is TableBoundaryKind.MIXED:
                warning_codes.append("table.mixed_boundary_evidence")
            evidence: Metadata = (
                ("row_band_count", str(len(row_group) + len(merged))),
                ("column_band_count", str(len(anchors))),
                ("horizontal_rule_count", str(horizontal)),
                ("vertical_rule_count", str(vertical)),
                ("merged_cell_signal_count", str(len(merged))),
                ("title_or_continuation_present", str(has_title).lower()),
                ("prose_like", str(prose_like).lower()),
            )
            selection = PageRegionSelection.for_bounding_box(
                detection_input.document.source,
                page.page_index,
                _padded_box(
                    region_box,
                    page.width,
                    page.height,
                    configuration.render_padding_points,
                ),
            )
            results.append(
                _ProvisionalRegion(
                    page_index=page.page_index,
                    box=region_box,
                    blocks=blocks,
                    row_count=len(row_group) + len(merged),
                    column_count=len(anchors),
                    column_anchors=tuple(
                        value / page.width for value in anchors
                    ),
                    rules=rules,
                    merged_block_ids=tuple(
                        record.block.block_id for record in merged
                    ),
                    associations=association_values,
                    source_label=label,
                    boundary_kind=boundary,
                    confidence=confidence,
                    evidence_status=status,
                    evidence=evidence,
                    warning_codes=tuple(warning_codes),
                    selection=selection,
                )
            )
            if len(results) > configuration.max_candidates * (
                configuration.max_regions_per_candidate
            ):
                raise TableDetectionLimitError(
                    "provisional table regions exceed their aggregate limit"
                )
    return tuple(
        sorted(results, key=lambda item: (item.page_index, item.box[1]))
    )


def _link_page_regions(
    regions: tuple[_ProvisionalRegion, ...],
    configuration: TableDetectionConfiguration,
) -> tuple[_ProvisionalCandidate, ...]:
    candidates: list[_ProvisionalCandidate] = []
    index = 0
    while index < len(regions):
        chain = [regions[index]]
        index += 1
        while index < len(regions) and _continues(chain[-1], regions[index]):
            chain.append(regions[index])
            index += 1
            if len(chain) > configuration.max_regions_per_candidate:
                raise TableDetectionLimitError(
                    "table regions exceed max_regions_per_candidate"
                )
        associations = tuple(
            association
            for region in chain
            for association in region.associations
        )
        if len(associations) > configuration.max_associations_per_candidate:
            raise TableDetectionLimitError(
                "table associations exceed their configured limit"
            )
        boundaries = {region.boundary_kind for region in chain}
        boundary = (
            next(iter(boundaries))
            if len(boundaries) == 1
            else TableBoundaryKind.MIXED
        )
        confidence = min(region.confidence for region in chain)
        status = (
            TableEvidenceStatus.AMBIGUOUS
            if any(
                region.evidence_status is TableEvidenceStatus.AMBIGUOUS
                for region in chain
            )
            else TableEvidenceStatus.PROPOSED
        )
        warning_code_values = [
            code for region in chain for code in region.warning_codes
        ]
        if len(boundaries) > 1:
            warning_code_values.append("table.mixed_boundary_evidence")
        warning_codes = tuple(dict.fromkeys(warning_code_values))
        source_label = next(
            (region.source_label for region in chain if region.source_label),
            None,
        )
        evidence: Metadata = (
            ("page_region_count", str(len(chain))),
            ("first_page_index", str(chain[0].page_index)),
            ("last_page_index", str(chain[-1].page_index)),
            ("explicit_continuation", str(len(chain) > 1).lower()),
        )
        key = stable_id(
            "provisional-table-candidate",
            tuple(
                (
                    region.page_index,
                    tuple(block.block.block_id for block in region.blocks),
                )
                for region in chain
            ),
        )
        candidates.append(
            _ProvisionalCandidate(
                key=key,
                regions=tuple(chain),
                associations=associations,
                source_label=source_label,
                boundary_kind=boundary,
                confidence=confidence,
                evidence_status=status,
                evidence=evidence,
                warning_codes=warning_codes,
            )
        )
    return tuple(candidates)


def _continues(left: _ProvisionalRegion, right: _ProvisionalRegion) -> bool:
    if right.page_index != left.page_index + 1:
        return False
    continuation = any(
        association.role is TableAssociationRole.CONTINUATION_LABEL
        for association in right.associations
    )
    if not continuation:
        return False
    if left.source_label is not None and right.source_label is None:
        return False
    if (
        left.source_label is not None
        and right.source_label is not None
        and _normalized_label(left.source_label)
        != _normalized_label(right.source_label)
    ):
        return False
    if left.column_count != right.column_count:
        return False
    return all(
        abs(a - b) <= 0.08
        for a, b in zip(left.column_anchors, right.column_anchors, strict=True)
    )


def _page_records(
    blocks: tuple[ExtractedBlock, ...], layout: PageLayoutResult
) -> tuple[_BlockRecord, ...]:
    by_id = {block.block_id: block for block in blocks}
    proposed = set(layout.proposed_order)
    ordered_ids = list(layout.proposed_order)
    ordered_ids.extend(
        block.block_id
        for block in blocks
        if block.kind == "text" and block.block_id not in proposed
    )
    records: list[_BlockRecord] = []
    for order, block_id in enumerate(ordered_ids):
        block = by_id[block_id]
        if not isinstance(block.text, str) or not block.text.strip():
            continue
        box = _block_box(block.source_spans)
        if box is None:
            continue
        records.append(
            _BlockRecord(
                block=block,
                page_index=layout.page_index,
                box=box,
                order=order,
                layout_confidence=(
                    layout.confidence if block_id in proposed else 0.35
                ),
            )
        )
    return tuple(records)


def _association_for_record(
    record: _BlockRecord,
) -> TableTextAssociation | None:
    text = record.block.text or ""
    title = _TABLE_TITLE.search(text)
    if title is not None:
        role = (
            TableAssociationRole.CONTINUATION_LABEL
            if _CONTINUED.search(text) is not None
            else TableAssociationRole.TITLE
        )
        return TableTextAssociation.create(
            role=role,
            page_index=record.page_index,
            block=record.block,
            confidence=0.95 if title.group("label") else 0.80,
            evidence=(("lexical_prefix", "table"),),
        )
    if _CAPTION.search(text) is not None:
        return TableTextAssociation.create(
            role=TableAssociationRole.CAPTION,
            page_index=record.page_index,
            block=record.block,
            confidence=0.85,
            evidence=(("lexical_prefix", "caption"),),
        )
    if _NOTE.search(text) is not None:
        return TableTextAssociation.create(
            role=TableAssociationRole.NOTE,
            page_index=record.page_index,
            block=record.block,
            confidence=0.90,
            evidence=(("lexical_prefix", "note_or_source"),),
        )
    return None


def _vertical_box_distance(left: BoundingBox, right: BoundingBox) -> float:
    if left[3] <= right[1]:
        return right[1] - left[3]
    if left[1] >= right[3]:
        return left[1] - right[3]
    return 0.0


def _nearby_associations(
    region_box: BoundingBox,
    records: tuple[_BlockRecord, ...],
    associations_by_id: dict[str, TableTextAssociation],
    maximum_distance: float,
) -> tuple[TableTextAssociation, ...]:
    values: list[tuple[int, TableTextAssociation]] = []
    for record in records:
        association = associations_by_id.get(record.block.block_id)
        if association is None:
            continue
        if record.box[2] < region_box[0] or record.box[0] > region_box[2]:
            continue
        distance = _vertical_box_distance(record.box, region_box)
        if distance <= maximum_distance:
            values.append((record.order, association))
    return tuple(association for _, association in sorted(values))


def _normalized_label(value: str) -> str:
    return " ".join(value.casefold().split())


def _source_label(
    associations: tuple[TableTextAssociation, ...],
) -> str | None:
    for association in associations:
        if association.role not in (
            TableAssociationRole.TITLE,
            TableAssociationRole.CONTINUATION_LABEL,
        ):
            continue
        match = _TABLE_TITLE.search(association.text)
        if match is not None and match.group("label"):
            return match.group(0).strip()
    return None


def _cluster_rows(
    records: tuple[_BlockRecord, ...], tolerance: float
) -> tuple[tuple[_BlockRecord, ...], ...]:
    rows: list[list[_BlockRecord]] = []
    centers: list[float] = []
    for record in sorted(
        records, key=lambda item: (item.center_y, item.box[0])
    ):
        if not rows or abs(record.center_y - centers[-1]) > tolerance:
            rows.append([record])
            centers.append(record.center_y)
        else:
            rows[-1].append(record)
            centers[-1] = sum(item.center_y for item in rows[-1]) / len(
                rows[-1]
            )
    return tuple(
        tuple(sorted(row, key=lambda item: item.box[0])) for row in rows
    )


def _group_qualifying_rows(
    rows: tuple[tuple[_BlockRecord, ...], ...], maximum_gap: float
) -> tuple[tuple[tuple[_BlockRecord, ...], ...], ...]:
    groups: list[list[tuple[_BlockRecord, ...]]] = []
    previous_center: float | None = None
    for row in rows:
        center = sum(record.center_y for record in row) / len(row)
        if previous_center is None or center - previous_center > maximum_gap:
            groups.append([row])
        else:
            groups[-1].append(row)
        previous_center = center
    return tuple(tuple(group) for group in groups)


def _cluster_values(
    values: tuple[float, ...], tolerance: float
) -> tuple[float, ...]:
    groups: list[list[float]] = []
    for value in sorted(values):
        if (
            not groups
            or abs(value - (sum(groups[-1]) / len(groups[-1]))) > tolerance
        ):
            groups.append([value])
        else:
            groups[-1].append(value)
    return tuple(sum(group) / len(group) for group in groups)


def _rows_support_columns(
    rows: tuple[tuple[_BlockRecord, ...], ...],
    anchors: tuple[float, ...],
    tolerance: float,
    minimum_columns: int,
) -> bool:
    for row in rows:
        matched = {
            min(
                range(len(anchors)),
                key=lambda index: abs(record.box[0] - anchors[index]),
            )
            for record in row
            if min(abs(record.box[0] - anchor) for anchor in anchors)
            <= tolerance
        }
        if len(matched) < minimum_columns:
            return False
    return True


def _merged_records(
    rows: tuple[tuple[_BlockRecord, ...], ...],
    base: tuple[_BlockRecord, ...],
    base_box: BoundingBox,
    anchors: tuple[float, ...],
    configuration: TableDetectionConfiguration,
) -> tuple[_BlockRecord, ...]:
    base_ids = {record.block.block_id for record in base}
    first_y = min(record.center_y for record in base)
    last_y = max(record.center_y for record in base)
    values: list[_BlockRecord] = []
    for row in rows:
        if len(row) != 1:
            continue
        record = row[0]
        if record.block.block_id in base_ids:
            continue
        if not (
            first_y - configuration.maximum_row_gap_points
            <= record.center_y
            <= last_y + configuration.maximum_row_gap_points
        ):
            continue
        center_x = (record.box[0] + record.box[2]) / 2.0
        if not base_box[0] <= center_x <= base_box[2]:
            continue
        if min(abs(record.box[0] - anchor) for anchor in anchors) <= (
            configuration.column_alignment_tolerance_points
        ):
            continue
        values.append(record)
    return tuple(sorted(values, key=lambda item: item.order))


def _region_confidence(
    boundary: TableBoundaryKind,
    *,
    has_title: bool,
    prose_like: bool,
) -> float:
    return min(
        1.0,
        0.60
        + (0.15 if has_title else 0.0)
        + (0.20 if boundary is TableBoundaryKind.RULED else 0.0)
        + (0.08 if boundary is TableBoundaryKind.MIXED else 0.0)
        - (0.30 if prose_like else 0.0),
    )


def _boundary_from_rules(
    rules: tuple[TableRuleSegment, ...],
) -> TableBoundaryKind:
    horizontal = sum(
        rule.orientation is TableRuleOrientation.HORIZONTAL for rule in rules
    )
    vertical = sum(
        rule.orientation is TableRuleOrientation.VERTICAL for rule in rules
    )
    if horizontal >= 2 and vertical >= 2:
        return TableBoundaryKind.RULED
    if horizontal or vertical:
        return TableBoundaryKind.MIXED
    return TableBoundaryKind.UNRULED


def _nearby_rules(
    block_box: BoundingBox,
    rules: tuple[TableRuleSegment, ...],
    proximity: float,
) -> tuple[TableRuleSegment, ...]:
    expanded = _expand_box(block_box, proximity)
    selected = [
        rule for rule in rules if _boxes_intersect(expanded, rule.bounding_box)
    ]
    if selected:
        closure = _expand_box(
            _union_boxes(
                tuple(rule.bounding_box for rule in selected) + (block_box,)
            ),
            proximity,
        )
        selected = [
            rule
            for rule in rules
            if _boxes_intersect(closure, rule.bounding_box)
        ]
    return tuple(selected)


def _materialize_warnings(
    candidates: tuple[TableCandidate, ...],
    provisional: tuple[_ProvisionalCandidate, ...],
) -> tuple[IngestionWarning, ...]:
    warnings: list[IngestionWarning] = []
    messages = {
        "table.ambiguous_candidate": (
            "Table-shaped geometry remains an ambiguous candidate"
        ),
        "table.prose_like_candidate": (
            "Long prose-like blocks weaken table evidence"
        ),
        "table.merged_cell_signal": (
            "A single-block row may represent merged-cell evidence"
        ),
        "table.mixed_boundary_evidence": (
            "Only partial horizontal or vertical rule evidence was observed"
        ),
    }
    for candidate, item in zip(candidates, provisional, strict=True):
        for code in item.warning_codes:
            warnings.append(
                IngestionWarning.create(
                    code=code,
                    severity=WarningSeverity.WARNING,
                    message=messages[code],
                    object_ids=(
                        candidate.candidate_id,
                        *(
                            region.region_evidence_id
                            for region in candidate.regions
                        ),
                    ),
                    source_spans=candidate.source_spans,
                    evidence=(("confidence", str(candidate.confidence)),),
                )
            )
    return tuple(warnings)


def detect_table_candidates(
    detector: _DetectorContext,
    document: ExtractedDocument,
    content: BinaryIO,
    layouts: tuple[PageLayoutResult, ...],
) -> TableDetectionResult:
    """Run detection using dependencies owned by the public facade."""
    return _DeterministicTableCandidateDetector.detect_with_layout(
        detector, document, content, layouts
    )

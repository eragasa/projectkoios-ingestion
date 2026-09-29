"""Phased implementation behind the stable page-layout facade."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from projectkoios.ingestion.layout import (
    LayoutAnalysisLimitError,
    LayoutBlockReference,
    LayoutConfiguration,
    LayoutExclusion,
    LayoutGroupHypothesis,
    LayoutGroupKind,
    LayoutPageKind,
    PageLayoutResult,
    _finite_float,
    _union_box,
    _validated_box,
)
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedPage,
    IngestionWarning,
    Metadata,
    SourceDocument,
    SourceSpan,
    WarningSeverity,
)
from projectkoios.ingestion.pdf.models import PYMUPDF_COORDINATE_SYSTEM

_ALGORITHM = "bounded_geometry_v2"


@dataclass(frozen=True)
class _Item:
    reference: LayoutBlockReference
    box: BoundingBox


@dataclass(frozen=True)
class _PreparedPage:
    references: tuple[LayoutBlockReference, ...]
    non_text_ids: tuple[str, ...]
    items: tuple[_Item, ...]
    exclusions: tuple[LayoutExclusion, ...]


class _LayoutPageAnalyzer:
    def __init__(
        self,
        *,
        configuration: LayoutConfiguration,
        processor_name: str,
        processor_version: str,
    ) -> None:
        self.configuration = configuration
        self.processor_name = processor_name
        self.processor_version = processor_version

    @property
    def configuration_digest(self) -> str:
        return self.configuration.configuration_digest

    def analyze(
        self, source: SourceDocument, page: ExtractedPage
    ) -> PageLayoutResult:
        self._preflight_page(source, page)
        self._validate_source_page(source, page)
        prepared = self._prepare_page(page)
        warnings = self._exclusion_warnings(source, page, prepared)
        items = list(prepared.items)
        exclusions = list(prepared.exclusions)

        if not items:
            return self._no_analyzable_text_result(
                source, page, prepared, warnings
            )
        if page.rotation_degrees != 0:
            warnings.append(
                self._warning(
                    source,
                    page,
                    code="layout.rotated_page_ambiguous",
                    message=(
                        "Nonzero page rotation lacks verified display-space "
                        "reading-order semantics"
                    ),
                    items=tuple(items),
                    object_ids=tuple(item.reference.block_id for item in items),
                    evidence=(
                        ("rotation_degrees", str(page.rotation_degrees)),
                        ("ordering", "unrotated_geometry_fallback"),
                    ),
                )
            )
            return self._ambiguous_result(
                source,
                page,
                prepared.references,
                prepared.non_text_ids,
                items,
                exclusions,
                warnings,
                evidence=(
                    ("algorithm", _ALGORITHM),
                    ("ambiguity", "nonzero_page_rotation"),
                    ("rotation_degrees", str(page.rotation_degrees)),
                ),
            )

        overlap_pairs = self._overlap_pairs(items)
        if overlap_pairs:
            warnings.append(
                self._warning(
                    source,
                    page,
                    code="layout.overlapping_blocks_ambiguous",
                    message=(
                        "Overlapping text blocks do not support a confident "
                        "geometry-only reading order"
                    ),
                    items=tuple(items),
                    object_ids=tuple(item.reference.block_id for item in items),
                    evidence=(("overlap_pair_count", str(overlap_pairs)),),
                )
            )
            return self._ambiguous_result(
                source,
                page,
                prepared.references,
                prepared.non_text_ids,
                items,
                exclusions,
                warnings,
                evidence=(
                    ("algorithm", _ALGORITHM),
                    ("ambiguity", "overlapping_text_boxes"),
                    ("overlap_pair_count", str(overlap_pairs)),
                ),
            )

        bottom_text, flow = self._split_bottom_text(items, page.height)
        bottom_warning_ids = self._record_bottom_text_warning(
            source, page, bottom_text, warnings
        )
        wide, narrow = self._split_wide(flow, page.width)
        split = self._best_column_split(narrow, page.width, page.height)
        if split is None:
            return self._analyze_unsplit_flow(
                source=source,
                page=page,
                prepared=prepared,
                items=items,
                exclusions=exclusions,
                warnings=warnings,
                flow=flow,
                bottom_text=bottom_text,
                bottom_warning_ids=bottom_warning_ids,
            )
        return self._analyze_split_flow(
            source=source,
            page=page,
            prepared=prepared,
            items=items,
            exclusions=exclusions,
            warnings=warnings,
            wide=wide,
            bottom_text=bottom_text,
            bottom_warning_ids=bottom_warning_ids,
            split=split,
        )

    def _prepare_page(self, page: ExtractedPage) -> _PreparedPage:
        text_blocks = tuple(
            block for block in page.blocks if block.kind == "text"
        )
        if len(text_blocks) > self.configuration.max_text_blocks_per_page:
            raise LayoutAnalysisLimitError(
                "text block count exceeds max_text_blocks_per_page "
                f"({self.configuration.max_text_blocks_per_page})"
            )
        references = tuple(
            LayoutBlockReference.from_block(block) for block in text_blocks
        )
        non_text_ids = tuple(
            block.block_id for block in page.blocks if block.kind != "text"
        )
        items: list[_Item] = []
        exclusions: list[LayoutExclusion] = []
        for block, reference in zip(text_blocks, references, strict=True):
            if not isinstance(block.text, str):
                exclusions.append(
                    LayoutExclusion(
                        block_id=reference.block_id,
                        reason="missing_text_payload",
                        evidence=(("text_payload", "not_a_string"),),
                    )
                )
                continue
            box = reference.bounding_box
            if box is None:
                exclusions.append(
                    LayoutExclusion(
                        block_id=reference.block_id,
                        reason="missing_bounding_box",
                        evidence=(
                            ("geometry", "not_available_for_every_span"),
                        ),
                    )
                )
                continue
            x0, y0, x1, y1 = box
            if x1 <= x0 or y1 <= y0:
                exclusions.append(
                    LayoutExclusion(
                        block_id=reference.block_id,
                        reason="non_positive_geometry",
                        evidence=(("bounding_box", _box_text(box)),),
                    )
                )
                continue
            items.append(_Item(reference, box))
        return _PreparedPage(
            references=references,
            non_text_ids=non_text_ids,
            items=tuple(items),
            exclusions=tuple(exclusions),
        )

    def _exclusion_warnings(
        self,
        source: SourceDocument,
        page: ExtractedPage,
        prepared: _PreparedPage,
    ) -> list[IngestionWarning]:
        if not prepared.exclusions:
            return []
        return [
            self._warning(
                source,
                page,
                code="layout.text_geometry_excluded",
                message=(
                    "Text blocks without usable positive-area geometry are "
                    "documented but excluded from the proposed order"
                ),
                items=(),
                object_ids=tuple(
                    exclusion.block_id for exclusion in prepared.exclusions
                ),
                evidence=(("excluded_count", str(len(prepared.exclusions))),),
            )
        ]

    def _no_analyzable_text_result(
        self,
        source: SourceDocument,
        page: ExtractedPage,
        prepared: _PreparedPage,
        warnings: list[IngestionWarning],
    ) -> PageLayoutResult:
        has_text = bool(prepared.references)
        return self._result(
            source=source,
            page=page,
            references=prepared.references,
            non_text_ids=prepared.non_text_ids,
            proposed_order=(),
            exclusions=prepared.exclusions,
            groups=(),
            page_kind=(
                LayoutPageKind.AMBIGUOUS if has_text else LayoutPageKind.EMPTY
            ),
            evidence=(
                ("algorithm", _ALGORITHM),
                ("analyzable_text_block_count", "0"),
                (
                    "unanalysable_text_block_count",
                    str(len(prepared.exclusions)),
                ),
                ("non_text_block_count", str(len(prepared.non_text_ids))),
            ),
            confidence=0.0 if has_text else 1.0,
            warnings=tuple(warnings),
        )

    def _record_bottom_text_warning(
        self,
        source: SourceDocument,
        page: ExtractedPage,
        bottom_text: list[_Item],
        warnings: list[IngestionWarning],
    ) -> tuple[str, ...]:
        if not bottom_text:
            return ()
        warning = self._warning(
            source,
            page,
            code="layout.separated_bottom_text_ambiguous",
            message=(
                "Separated bottom text may be a footnote, footer, or "
                "final sparse paragraph"
            ),
            items=tuple(bottom_text),
            object_ids=tuple(item.reference.block_id for item in bottom_text),
            evidence=(
                ("hypothesis", "footnote_candidate"),
                ("semantic_role", "unverified"),
            ),
        )
        warnings.append(warning)
        return (warning.warning_id,)

    def _analyze_unsplit_flow(
        self,
        *,
        source: SourceDocument,
        page: ExtractedPage,
        prepared: _PreparedPage,
        items: list[_Item],
        exclusions: list[LayoutExclusion],
        warnings: list[IngestionWarning],
        flow: list[_Item],
        bottom_text: list[_Item],
        bottom_warning_ids: tuple[str, ...],
    ) -> PageLayoutResult:
        separated = self._separated_group_conflict(flow, page.width)
        if separated:
            warnings.append(
                self._warning(
                    source,
                    page,
                    code="layout.discontinuous_side_groups_ambiguous",
                    message=(
                        "Separated horizontal groups lack sufficient actual "
                        "vertical flow concurrency"
                    ),
                    items=tuple(items),
                    object_ids=tuple(item.reference.block_id for item in items),
                    evidence=(
                        ("candidate_split_count", str(separated)),
                        ("column_support", "insufficient"),
                    ),
                )
            )
            return self._ambiguous_result(
                source,
                page,
                prepared.references,
                prepared.non_text_ids,
                items,
                exclusions,
                warnings,
                evidence=(
                    ("algorithm", _ALGORITHM),
                    ("ambiguity", "discontinuous_side_groups"),
                ),
            )

        bridging = self._bridging_conflict(flow, page.width, page.height)
        if bridging:
            warnings.append(
                self._warning(
                    source,
                    page,
                    code="layout.bridging_block_ambiguous",
                    message=(
                        "A top block bridges concurrent side groups without "
                        "sufficient spanning-heading evidence"
                    ),
                    items=tuple(items),
                    object_ids=tuple(item.reference.block_id for item in items),
                    evidence=(("bridging_block_count", str(bridging)),),
                )
            )
            return self._ambiguous_result(
                source,
                page,
                prepared.references,
                prepared.non_text_ids,
                items,
                exclusions,
                warnings,
                evidence=(
                    ("algorithm", _ALGORITHM),
                    ("ambiguity", "bridging_top_block"),
                ),
            )

        ordered_flow = sorted(flow, key=_geometric_key)
        groups = (
            [
                self._group(
                    source,
                    page,
                    LayoutGroupKind.ONE_COLUMN,
                    ordered_flow,
                    (
                        ("ordering", "top_then_left"),
                        ("column_split", "none"),
                    ),
                    0.90,
                )
            ]
            if ordered_flow
            else []
        )
        groups.extend(
            self._bottom_text_groups(
                source, page, bottom_text, bottom_warning_ids
            )
        )
        order = tuple(
            item.reference.block_id
            for item in [
                *ordered_flow,
                *sorted(bottom_text, key=_geometric_key),
            ]
        )
        return self._result(
            source=source,
            page=page,
            references=prepared.references,
            non_text_ids=prepared.non_text_ids,
            proposed_order=order,
            exclusions=tuple(exclusions),
            groups=tuple(groups),
            page_kind=(
                LayoutPageKind.AMBIGUOUS
                if bottom_text
                else LayoutPageKind.ONE_COLUMN
            ),
            evidence=(
                ("algorithm", _ALGORITHM),
                ("column_count", "1"),
                ("bottom_text_block_count", str(len(bottom_text))),
                ("non_text_block_count", str(len(prepared.non_text_ids))),
            ),
            confidence=(
                0.35 if bottom_text else (0.90 if not exclusions else 0.70)
            ),
            warnings=tuple(warnings),
        )

    def _analyze_split_flow(
        self,
        *,
        source: SourceDocument,
        page: ExtractedPage,
        prepared: _PreparedPage,
        items: list[_Item],
        exclusions: list[LayoutExclusion],
        warnings: list[IngestionWarning],
        wide: list[_Item],
        bottom_text: list[_Item],
        bottom_warning_ids: tuple[str, ...],
        split: tuple[list[_Item], list[_Item], float, float],
    ) -> PageLayoutResult:
        left, right, gap, overlap_ratio = split
        minimum_gap = self.configuration.minimum_column_gap_ratio * page.width
        if gap < minimum_gap:
            warnings.append(
                self._warning(
                    source,
                    page,
                    code="layout.weak_column_separation_ambiguous",
                    message=(
                        "Vertically concurrent text groups have too little "
                        "horizontal separation for a confident column order"
                    ),
                    items=tuple(items),
                    object_ids=tuple(item.reference.block_id for item in items),
                    evidence=(
                        ("column_gap_points", _number(gap)),
                        ("minimum_column_gap_points", _number(minimum_gap)),
                    ),
                )
            )
            return self._ambiguous_result(
                source,
                page,
                prepared.references,
                prepared.non_text_ids,
                items,
                exclusions,
                warnings,
                evidence=(
                    ("algorithm", _ALGORITHM),
                    ("ambiguity", "weak_column_separation"),
                    ("column_gap_points", _number(gap)),
                ),
            )

        nested_splits = (
            self._best_column_split(left, page.width, page.height),
            self._best_column_split(right, page.width, page.height),
        )
        if any(
            nested is not None and nested[2] >= minimum_gap
            for nested in nested_splits
        ):
            warnings.append(
                self._warning(
                    source,
                    page,
                    code="layout.multiple_column_groups_ambiguous",
                    message=(
                        "More than two concurrent horizontal groups exceed "
                        "the processor's confident column model"
                    ),
                    items=tuple(items),
                    object_ids=tuple(item.reference.block_id for item in items),
                    evidence=(("supported_confident_column_count", "2"),),
                )
            )
            return self._ambiguous_result(
                source,
                page,
                prepared.references,
                prepared.non_text_ids,
                items,
                exclusions,
                warnings,
                evidence=(
                    ("algorithm", _ALGORITHM),
                    ("ambiguity", "more_than_two_column_groups"),
                ),
            )

        spanning, unsupported_wide = self._classify_spanning_items(
            wide, left, right
        )
        if unsupported_wide or len(spanning) > 1:
            warning_items = (
                [*unsupported_wide, *spanning]
                if len(spanning) > 1
                else unsupported_wide
            )
            warnings.append(
                self._warning(
                    source,
                    page,
                    code="layout.spanning_position_ambiguous",
                    message=(
                        "Wide text crosses candidate columns away from the "
                        "supported heading position"
                    ),
                    items=tuple(warning_items),
                    object_ids=tuple(
                        item.reference.block_id for item in warning_items
                    ),
                    evidence=(
                        (
                            "unsupported_wide_count",
                            str(len(unsupported_wide)),
                        ),
                        ("spanning_candidate_count", str(len(spanning))),
                    ),
                )
            )
            return self._ambiguous_result(
                source,
                page,
                prepared.references,
                prepared.non_text_ids,
                items,
                exclusions,
                warnings,
                evidence=(
                    ("algorithm", _ALGORITHM),
                    ("ambiguity", "unsupported_spanning_position"),
                ),
            )

        left_width = _horizontal_extent(left)
        right_width = _horizontal_extent(right)
        width_balance = min(left_width, right_width) / max(
            left_width, right_width
        )
        sidebar = (
            width_balance < self.configuration.balanced_column_width_ratio
            and min(left_width, right_width) / page.width
            < self.configuration.sidebar_width_ratio
        )
        if sidebar:
            return self._sidebar_result(
                source=source,
                page=page,
                prepared=prepared,
                exclusions=exclusions,
                warnings=warnings,
                left=left,
                right=right,
                left_width=left_width,
                right_width=right_width,
                width_balance=width_balance,
                spanning=spanning,
                bottom_text=bottom_text,
                bottom_warning_ids=bottom_warning_ids,
                gap=gap,
            )
        return self._two_column_result(
            source=source,
            page=page,
            prepared=prepared,
            exclusions=exclusions,
            warnings=warnings,
            left=left,
            right=right,
            spanning=spanning,
            bottom_text=bottom_text,
            bottom_warning_ids=bottom_warning_ids,
            gap=gap,
            overlap_ratio=overlap_ratio,
        )

    @staticmethod
    def _classify_spanning_items(
        wide: list[_Item], left: list[_Item], right: list[_Item]
    ) -> tuple[list[_Item], list[_Item]]:
        column_top = min(
            min(item.box[1] for item in left),
            min(item.box[1] for item in right),
        )
        left_extent = max(item.box[2] for item in left)
        right_extent = min(item.box[0] for item in right)
        spanning = [
            item
            for item in wide
            if item.box[3] <= column_top
            and item.box[0] < left_extent
            and item.box[2] > right_extent
        ]
        return spanning, [item for item in wide if item not in spanning]

    def _sidebar_result(
        self,
        *,
        source: SourceDocument,
        page: ExtractedPage,
        prepared: _PreparedPage,
        exclusions: list[LayoutExclusion],
        warnings: list[IngestionWarning],
        left: list[_Item],
        right: list[_Item],
        left_width: float,
        right_width: float,
        width_balance: float,
        spanning: list[_Item],
        bottom_text: list[_Item],
        bottom_warning_ids: tuple[str, ...],
        gap: float,
    ) -> PageLayoutResult:
        sidebar_items, main_items = (
            (left, right) if left_width < right_width else (right, left)
        )
        warning = self._warning(
            source,
            page,
            code="layout.sidebar_order_ambiguous",
            message=(
                "A narrow side group is retained as an uncertain sidebar "
                "hypothesis rather than assigned a confident flow position"
            ),
            items=tuple(sidebar_items),
            object_ids=tuple(item.reference.block_id for item in sidebar_items),
            evidence=(
                ("column_width_balance", _number(width_balance)),
                (
                    "narrow_width_points",
                    _number(min(left_width, right_width)),
                ),
            ),
        )
        warnings.append(warning)
        sorted_spanning = sorted(spanning, key=_geometric_key)
        middle = sorted([*main_items, *sidebar_items], key=_geometric_key)
        sorted_bottom_text = sorted(bottom_text, key=_geometric_key)
        groups: list[LayoutGroupHypothesis] = []
        if sorted_spanning:
            groups.append(
                self._group(
                    source,
                    page,
                    LayoutGroupKind.SPANNING_HEADING,
                    sorted_spanning,
                    (("position", "above_concurrent_columns"),),
                    0.85,
                )
            )
        groups.append(
            self._group(
                source,
                page,
                LayoutGroupKind.COLUMN,
                sorted(main_items, key=_geometric_key),
                (("role", "main_flow_candidate"),),
                0.45,
            )
        )
        groups.append(
            self._group(
                source,
                page,
                LayoutGroupKind.SIDEBAR,
                sorted(sidebar_items, key=_geometric_key),
                (
                    ("role", "narrow_concurrent_side_group"),
                    ("ordering", "uncertain"),
                ),
                0.35,
                (warning.warning_id,),
            )
        )
        groups.extend(
            self._bottom_text_groups(
                source, page, bottom_text, bottom_warning_ids
            )
        )
        order_items = [*sorted_spanning, *middle, *sorted_bottom_text]
        return self._result(
            source=source,
            page=page,
            references=prepared.references,
            non_text_ids=prepared.non_text_ids,
            proposed_order=tuple(
                item.reference.block_id for item in order_items
            ),
            exclusions=tuple(exclusions),
            groups=tuple(groups),
            page_kind=LayoutPageKind.AMBIGUOUS,
            evidence=(
                ("algorithm", _ALGORITHM),
                ("hypothesis", "main_flow_with_sidebar"),
                ("ordering", "geometric_and_explicitly_uncertain"),
                ("column_gap_points", _number(gap)),
            ),
            confidence=0.35,
            warnings=tuple(warnings),
        )

    def _two_column_result(
        self,
        *,
        source: SourceDocument,
        page: ExtractedPage,
        prepared: _PreparedPage,
        exclusions: list[LayoutExclusion],
        warnings: list[IngestionWarning],
        left: list[_Item],
        right: list[_Item],
        spanning: list[_Item],
        bottom_text: list[_Item],
        bottom_warning_ids: tuple[str, ...],
        gap: float,
        overlap_ratio: float,
    ) -> PageLayoutResult:
        sorted_spanning = sorted(spanning, key=_geometric_key)
        sorted_left = sorted(left, key=_geometric_key)
        sorted_right = sorted(right, key=_geometric_key)
        sorted_bottom_text = sorted(bottom_text, key=_geometric_key)
        confidence = min(0.95, 0.72 + gap / page.width)
        groups: list[LayoutGroupHypothesis] = []
        if sorted_spanning:
            groups.append(
                self._group(
                    source,
                    page,
                    LayoutGroupKind.SPANNING_HEADING,
                    sorted_spanning,
                    (
                        ("position", "above_concurrent_columns"),
                        (
                            "minimum_width_ratio",
                            _number(self.configuration.spanning_width_ratio),
                        ),
                    ),
                    confidence,
                )
            )
        groups.extend(
            (
                self._group(
                    source,
                    page,
                    LayoutGroupKind.COLUMN,
                    sorted_left,
                    (("column_index", "0"), ("ordering", "top_then_left")),
                    confidence,
                ),
                self._group(
                    source,
                    page,
                    LayoutGroupKind.COLUMN,
                    sorted_right,
                    (("column_index", "1"), ("ordering", "top_then_left")),
                    confidence,
                ),
            )
        )
        groups.extend(
            self._bottom_text_groups(
                source, page, bottom_text, bottom_warning_ids
            )
        )
        order_items = [
            *sorted_spanning,
            *sorted_left,
            *sorted_right,
            *sorted_bottom_text,
        ]
        return self._result(
            source=source,
            page=page,
            references=prepared.references,
            non_text_ids=prepared.non_text_ids,
            proposed_order=tuple(
                item.reference.block_id for item in order_items
            ),
            exclusions=tuple(exclusions),
            groups=tuple(groups),
            page_kind=(
                LayoutPageKind.AMBIGUOUS
                if bottom_text
                else LayoutPageKind.MULTI_COLUMN
            ),
            evidence=(
                ("algorithm", _ALGORITHM),
                ("column_count", "2"),
                ("column_gap_points", _number(gap)),
                ("vertical_overlap_ratio", _number(overlap_ratio)),
                ("bottom_text_block_count", str(len(bottom_text))),
                ("non_text_block_count", str(len(prepared.non_text_ids))),
            ),
            confidence=(
                0.35
                if bottom_text
                else (confidence if not exclusions else min(confidence, 0.70))
            ),
            warnings=tuple(warnings),
        )

    def _result(
        self,
        *,
        source: SourceDocument,
        page: ExtractedPage,
        references: tuple[LayoutBlockReference, ...],
        non_text_ids: tuple[str, ...],
        proposed_order: tuple[str, ...],
        exclusions: tuple[LayoutExclusion, ...],
        groups: tuple[LayoutGroupHypothesis, ...],
        page_kind: LayoutPageKind,
        evidence: Metadata,
        confidence: float,
        warnings: tuple[IngestionWarning, ...],
    ) -> PageLayoutResult:
        return PageLayoutResult.create(
            source=source,
            page=page,
            input_text_blocks=references,
            non_text_block_ids=non_text_ids,
            proposed_order=proposed_order,
            exclusions=exclusions,
            groups=groups,
            page_kind=page_kind,
            evidence=evidence,
            confidence=confidence,
            warnings=warnings,
            processor_name=self.processor_name,
            processor_version=self.processor_version,
            configuration_digest=self.configuration_digest,
        )

    def _preflight_page(
        self, source: SourceDocument, page: ExtractedPage
    ) -> None:
        if len(page.blocks) > self.configuration.max_raw_blocks_per_page:
            raise LayoutAnalysisLimitError(
                "raw block count exceeds max_raw_blocks_per_page "
                f"({self.configuration.max_raw_blocks_per_page})"
            )
        text_block_count = 0
        source_span_count = 0
        identity_character_count = 0

        def count_identity(value: str | None, name: str) -> None:
            nonlocal identity_character_count
            if value is None:
                return
            length = len(value)
            if length > self.configuration.max_identity_field_characters:
                raise LayoutAnalysisLimitError(
                    f"{name} exceeds max_identity_field_characters "
                    f"({self.configuration.max_identity_field_characters})"
                )
            identity_character_count += length
            if (
                identity_character_count
                > self.configuration.max_total_identity_characters
            ):
                raise LayoutAnalysisLimitError(
                    "identity character count exceeds "
                    "max_total_identity_characters "
                    f"({self.configuration.max_total_identity_characters})"
                )

        count_identity(source.source_id, "source_id")
        count_identity(source.blob_id, "source_blob_id")
        count_identity(page.coordinate_system, "coordinate_system")
        count_identity(page.printed_page_label, "printed_page_label")
        for block in page.blocks:
            if block.kind == "text":
                text_block_count += 1
                if (
                    text_block_count
                    > self.configuration.max_text_blocks_per_page
                ):
                    raise LayoutAnalysisLimitError(
                        "text block count exceeds max_text_blocks_per_page "
                        f"({self.configuration.max_text_blocks_per_page})"
                    )
            count_identity(block.block_id, "block_id")
            count_identity(block.kind, "block_kind")
            for span in block.source_spans:
                source_span_count += 1
                if (
                    source_span_count
                    > self.configuration.max_source_spans_per_page
                ):
                    raise LayoutAnalysisLimitError(
                        "source span count exceeds "
                        "max_source_spans_per_page "
                        f"({self.configuration.max_source_spans_per_page})"
                    )
                count_identity(span.source_id, "span.source_id")
                count_identity(span.source_blob_id, "span.source_blob_id")
                count_identity(span.source_object_id, "span.source_object_id")
                count_identity(
                    span.printed_page_label, "span.printed_page_label"
                )
        if page.coordinate_system != PYMUPDF_COORDINATE_SYSTEM:
            raise ValueError(
                "layout requires the PyMuPDF unrotated crop-box coordinate "
                "system"
            )

    @staticmethod
    def _validate_source_page(
        source: SourceDocument, page: ExtractedPage
    ) -> None:
        width = _finite_float(page.width, "page width")
        height = _finite_float(page.height, "page height")
        if width <= 0.0 or height <= 0.0:
            raise ValueError("layout page dimensions must be positive")
        raw_ids = tuple(block.block_id for block in page.blocks)
        if len(set(raw_ids)) != len(raw_ids):
            raise ValueError("layout input page block IDs must be unique")
        if any(not block_id for block_id in raw_ids):
            raise ValueError("layout input page block IDs must be non-empty")
        for block in page.blocks:
            for span in block.source_spans:
                if (
                    span.source_id != source.source_id
                    or span.source_blob_id != source.blob_id
                    or span.page_index != page.page_index
                ):
                    raise ValueError(
                        "layout input does not match the exact source page"
                    )
                if span.printed_page_label != page.printed_page_label:
                    raise ValueError(
                        "layout input span label differs from its page"
                    )
                if span.bounding_box is not None:
                    box = _validated_box(span.bounding_box, positive_area=False)
                    if (
                        box[0] < 0.0
                        or box[1] < 0.0
                        or box[2] > width
                        or box[3] > height
                    ):
                        raise ValueError(
                            "layout input geometry lies outside the page"
                        )

    @staticmethod
    def _overlap_pairs(items: list[_Item]) -> int:
        count = 0
        for index, first in enumerate(items):
            for second in items[index + 1 :]:
                horizontal = min(first.box[2], second.box[2]) - max(
                    first.box[0], second.box[0]
                )
                vertical = min(first.box[3], second.box[3]) - max(
                    first.box[1], second.box[1]
                )
                if horizontal > 0.0 and vertical > 0.0:
                    count += 1
        return count

    def _split_bottom_text(
        self, items: list[_Item], page_height: float
    ) -> tuple[list[_Item], list[_Item]]:
        candidates = [
            item
            for item in items
            if item.box[1] / page_height
            >= self.configuration.footnote_start_ratio
        ]
        flow = [item for item in items if item not in candidates]
        if not candidates or not flow:
            return [], items
        gap = min(item.box[1] for item in candidates) - max(
            item.box[3] for item in flow
        )
        if gap < self.configuration.minimum_footnote_gap_ratio * page_height:
            return [], items
        return candidates, flow

    def _split_wide(
        self, items: list[_Item], page_width: float
    ) -> tuple[list[_Item], list[_Item]]:
        wide = [
            item
            for item in items
            if (item.box[2] - item.box[0]) / page_width
            >= self.configuration.spanning_width_ratio
        ]
        return wide, [item for item in items if item not in wide]

    @staticmethod
    def _separated_group_conflict(items: list[_Item], page_width: float) -> int:
        del page_width
        if len(items) < 2:
            return 0
        ordered = sorted(
            items,
            key=lambda item: (
                item.box[0],
                item.box[2],
                item.reference.block_id,
            ),
        )
        count = 0
        for index in range(1, len(ordered)):
            left_edge = max(item.box[2] for item in ordered[:index])
            right_edge = min(item.box[0] for item in ordered[index:])
            if right_edge - left_edge >= 0.0:
                count += 1
        return count

    def _column_support(
        self,
        left: list[_Item],
        right: list[_Item],
        page_height: float,
    ) -> float | None:
        left_extent = max(item.box[3] for item in left) - min(
            item.box[1] for item in left
        )
        right_extent = max(item.box[3] for item in right) - min(
            item.box[1] for item in right
        )
        if (
            left_extent / page_height
            <= self.configuration.minimum_column_flow_ratio
            or right_extent / page_height
            <= self.configuration.minimum_column_flow_ratio
        ):
            return None
        left_support = [
            max(_vertical_overlap_ratio(item, other) for other in right)
            for item in left
        ]
        right_support = [
            max(_vertical_overlap_ratio(item, other) for other in left)
            for item in right
        ]
        support = min(*left_support, *right_support)
        if support < self.configuration.minimum_vertical_overlap_ratio:
            return None
        return support

    def _bridging_conflict(
        self,
        items: list[_Item],
        page_width: float,
        page_height: float,
    ) -> int:
        count = 0
        for bridge in items:
            remaining = [item for item in items if item is not bridge]
            split = self._best_column_split(remaining, page_width, page_height)
            if split is None:
                continue
            left, right, gap, _ = split
            if gap < self.configuration.minimum_column_gap_ratio * page_width:
                continue
            column_top = min(
                min(item.box[1] for item in left),
                min(item.box[1] for item in right),
            )
            left_edge = max(item.box[2] for item in left)
            right_edge = min(item.box[0] for item in right)
            if (
                bridge.box[3] <= column_top
                and bridge.box[0] < left_edge
                and bridge.box[2] > right_edge
            ):
                count += 1
        return count

    def _best_column_split(
        self,
        items: list[_Item],
        page_width: float,
        page_height: float,
    ) -> tuple[list[_Item], list[_Item], float, float] | None:
        del page_width
        if len(items) < 2:
            return None
        ordered = sorted(
            items,
            key=lambda item: (
                item.box[0],
                item.box[2],
                item.reference.block_id,
            ),
        )
        best: tuple[list[_Item], list[_Item], float, float] | None = None
        for index in range(1, len(ordered)):
            left = ordered[:index]
            right = ordered[index:]
            left_edge = max(item.box[2] for item in left)
            right_edge = min(item.box[0] for item in right)
            gap = right_edge - left_edge
            if gap < 0.0:
                continue
            overlap_ratio = self._column_support(left, right, page_height)
            if overlap_ratio is None:
                continue
            candidate = (left, right, gap, overlap_ratio)
            if best is None or (gap, -index) > (best[2], -len(best[0])):
                best = candidate
        return best

    def _ambiguous_result(
        self,
        source: SourceDocument,
        page: ExtractedPage,
        references: tuple[LayoutBlockReference, ...],
        non_text_ids: tuple[str, ...],
        items: list[_Item],
        exclusions: list[LayoutExclusion],
        warnings: list[IngestionWarning],
        *,
        evidence: Metadata,
    ) -> PageLayoutResult:
        ordered = sorted(items, key=_geometric_key)
        ordered_ids = {item.reference.block_id for item in ordered}
        warning_ids = tuple(
            warning.warning_id
            for warning in warnings
            if ordered_ids.intersection(warning.object_ids)
        )
        group = self._group(
            source,
            page,
            LayoutGroupKind.UNCERTAIN,
            ordered,
            (
                ("ordering", "top_then_left_fallback"),
                ("certainty", "ambiguous"),
            ),
            0.25,
            warning_ids,
        )
        return self._result(
            source=source,
            page=page,
            references=references,
            non_text_ids=non_text_ids,
            proposed_order=tuple(item.reference.block_id for item in ordered),
            exclusions=tuple(exclusions),
            groups=(group,),
            page_kind=LayoutPageKind.AMBIGUOUS,
            evidence=evidence,
            confidence=0.25,
            warnings=tuple(warnings),
        )

    def _bottom_text_groups(
        self,
        source: SourceDocument,
        page: ExtractedPage,
        bottom_text: list[_Item],
        warning_ids: tuple[str, ...],
    ) -> list[LayoutGroupHypothesis]:
        if not bottom_text:
            return []
        return [
            self._group(
                source,
                page,
                LayoutGroupKind.FOOTNOTE_CANDIDATE,
                sorted(bottom_text, key=_geometric_key),
                (
                    ("position", "separated_near_page_bottom"),
                    ("role", "footnote_candidate"),
                    ("semantic_role", "unverified"),
                    ("ordering", "after_main_flow_fallback"),
                ),
                0.35,
                warning_ids,
            )
        ]

    @staticmethod
    def _group(
        source: SourceDocument,
        page: ExtractedPage,
        kind: LayoutGroupKind,
        items: Sequence[_Item],
        evidence: Metadata,
        confidence: float,
        warning_ids: tuple[str, ...] = (),
    ) -> LayoutGroupHypothesis:
        return LayoutGroupHypothesis.create(
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            page_index=page.page_index,
            kind=kind,
            block_ids=tuple(item.reference.block_id for item in items),
            bounding_box=_union_box(tuple(item.box for item in items)),
            evidence=evidence,
            confidence=confidence,
            warning_ids=warning_ids,
        )

    @staticmethod
    def _warning(
        source: SourceDocument,
        page: ExtractedPage,
        *,
        code: str,
        message: str,
        items: tuple[_Item, ...],
        object_ids: tuple[str, ...],
        evidence: Metadata,
    ) -> IngestionWarning:
        spans = tuple(
            span for item in items for span in item.reference.source_spans
        )
        if not spans:
            spans = (
                SourceSpan(
                    source_id=source.source_id,
                    source_blob_id=source.blob_id,
                    page_index=page.page_index,
                    printed_page_label=page.printed_page_label,
                ),
            )
        return IngestionWarning.create(
            code=code,
            severity=WarningSeverity.INFO,
            message=message,
            object_ids=object_ids,
            source_spans=spans,
            evidence=evidence,
            suggested_recovery="Inspect the raw blocks and rendered page",
        )


def analyze_layout_page(
    source: SourceDocument,
    page: ExtractedPage,
    *,
    configuration: LayoutConfiguration,
    processor_name: str,
    processor_version: str,
) -> PageLayoutResult:
    """Run one bounded deterministic page-layout analysis."""
    return _LayoutPageAnalyzer(
        configuration=configuration,
        processor_name=processor_name,
        processor_version=processor_version,
    ).analyze(source, page)


def _horizontal_extent(items: list[_Item]) -> float:
    return max(item.box[2] for item in items) - min(
        item.box[0] for item in items
    )


def _geometric_key(item: _Item) -> tuple[float, float, float, float, str]:
    return (
        item.box[1],
        item.box[0],
        item.box[3],
        item.box[2],
        item.reference.block_id,
    )


def _vertical_overlap_ratio(first: _Item, second: _Item) -> float:
    overlap = min(first.box[3], second.box[3]) - max(
        first.box[1], second.box[1]
    )
    if overlap <= 0.0:
        return 0.0
    return overlap / min(
        first.box[3] - first.box[1],
        second.box[3] - second.box[1],
    )


def _number(value: float) -> str:
    normalized = 0.0 if value == 0.0 else value
    return format(normalized, ".6g")


def _box_text(box: BoundingBox) -> str:
    return ",".join(_number(value) for value in box)

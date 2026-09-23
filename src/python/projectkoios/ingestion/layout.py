from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from projectkoios.ingestion.base import BasePageLayoutProcessor
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    IngestionWarning,
    Metadata,
    SourceDocument,
    SourceSpan,
    WarningSeverity,
)
from projectkoios.ingestion.pdf.models import PYMUPDF_COORDINATE_SYSTEM

LAYOUT_CONTRACT_VERSION = "1.0"


class LayoutAnalysisLimitError(ValueError):
    """Raised before layout analysis when a configured bound is exceeded."""


class LayoutPageKind(StrEnum):
    """The page-level geometry hypothesis."""

    EMPTY = "empty"
    ONE_COLUMN = "one_column"
    MULTI_COLUMN = "multi_column"
    AMBIGUOUS = "ambiguous"


class LayoutGroupKind(StrEnum):
    """A geometry-supported role for a group of text blocks."""

    ONE_COLUMN = "one_column"
    COLUMN = "column"
    SPANNING_HEADING = "spanning_heading"
    FOOTNOTE_CANDIDATE = "footnote_candidate"
    SIDEBAR = "sidebar"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class LayoutConfiguration:
    """Deterministic geometry thresholds and the page complexity bound."""

    max_raw_blocks_per_page: int = 1_024
    max_text_blocks_per_page: int = 512
    max_source_spans_per_page: int = 2_048
    max_identity_field_characters: int = 4_096
    max_total_identity_characters: int = 1_000_000
    minimum_column_gap_ratio: float = 0.04
    minimum_vertical_overlap_ratio: float = 0.25
    minimum_column_flow_ratio: float = 0.10
    spanning_width_ratio: float = 0.50
    footnote_start_ratio: float = 0.78
    minimum_footnote_gap_ratio: float = 0.025
    sidebar_width_ratio: float = 0.28
    balanced_column_width_ratio: float = 0.62

    def __post_init__(self) -> None:
        integer_fields = (
            ("max_raw_blocks_per_page", self.max_raw_blocks_per_page),
            ("max_text_blocks_per_page", self.max_text_blocks_per_page),
            ("max_source_spans_per_page", self.max_source_spans_per_page),
            (
                "max_identity_field_characters",
                self.max_identity_field_characters,
            ),
            (
                "max_total_identity_characters",
                self.max_total_identity_characters,
            ),
        )
        for name, value in integer_fields:
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
            ):
                raise ValueError(f"{name} must be positive")
        ratio_fields = (
            "minimum_column_gap_ratio",
            "minimum_vertical_overlap_ratio",
            "minimum_column_flow_ratio",
            "spanning_width_ratio",
            "footnote_start_ratio",
            "minimum_footnote_gap_ratio",
            "sidebar_width_ratio",
            "balanced_column_width_ratio",
        )
        for name in ratio_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError(f"{name} must be a finite ratio")
            normalized = float(value)
            if not math.isfinite(normalized) or not 0.0 < normalized < 1.0:
                raise ValueError(f"{name} must be between zero and one")
            object.__setattr__(self, name, normalized)

    @property
    def configuration_digest(self) -> str:
        return stable_id(
            "configuration",
            {
                "max_raw_blocks_per_page": self.max_raw_blocks_per_page,
                "max_text_blocks_per_page": self.max_text_blocks_per_page,
                "max_source_spans_per_page": self.max_source_spans_per_page,
                "max_identity_field_characters": (
                    self.max_identity_field_characters
                ),
                "max_total_identity_characters": (
                    self.max_total_identity_characters
                ),
                "minimum_column_gap_ratio": self.minimum_column_gap_ratio,
                "minimum_vertical_overlap_ratio": (
                    self.minimum_vertical_overlap_ratio
                ),
                "minimum_column_flow_ratio": self.minimum_column_flow_ratio,
                "spanning_width_ratio": self.spanning_width_ratio,
                "footnote_start_ratio": self.footnote_start_ratio,
                "minimum_footnote_gap_ratio": (self.minimum_footnote_gap_ratio),
                "sidebar_width_ratio": self.sidebar_width_ratio,
                "balanced_column_width_ratio": (
                    self.balanced_column_width_ratio
                ),
            },
        )


@dataclass(frozen=True)
class LayoutBlockReference:
    """A non-owning reference to one raw text block and its source spans."""

    block_id: str
    kind: str
    source_spans: tuple[SourceSpan, ...]

    @classmethod
    def from_block(cls, block: ExtractedBlock) -> LayoutBlockReference:
        return cls(
            block_id=block.block_id,
            kind=block.kind,
            source_spans=block.source_spans,
        )

    def __post_init__(self) -> None:
        if not self.block_id:
            raise ValueError("layout block reference ID must be non-empty")
        if not self.kind:
            raise ValueError("layout block reference kind must be non-empty")
        _require_tuple("source_spans", self.source_spans)
        if not self.source_spans:
            raise ValueError("layout block reference must retain source spans")
        normalized = tuple(_normalized_span(span) for span in self.source_spans)
        object.__setattr__(self, "source_spans", normalized)

    @property
    def bounding_box(self) -> BoundingBox | None:
        boxes = tuple(
            span.bounding_box
            for span in self.source_spans
            if span.bounding_box is not None
        )
        if len(boxes) != len(self.source_spans):
            return None
        return _union_box(boxes)

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.block_id,
            self.kind,
            tuple(span.identity_parts() for span in self.source_spans),
        )


@dataclass(frozen=True)
class LayoutExclusion:
    """A text block explicitly omitted from geometry-based ordering."""

    block_id: str
    reason: str
    evidence: Metadata

    def __post_init__(self) -> None:
        if not self.block_id or not self.reason:
            raise ValueError(
                "layout exclusion identity and reason are required"
            )
        _validate_metadata(self.evidence, required=True)

    def identity_parts(self) -> tuple[object, ...]:
        return (self.block_id, self.reason, self.evidence)


@dataclass(frozen=True)
class LayoutGroupHypothesis:
    """A column or special-flow hypothesis backed only by page geometry."""

    group_id: str
    source_id: str
    source_blob_id: str
    page_index: int
    kind: LayoutGroupKind
    block_ids: tuple[str, ...]
    bounding_box: BoundingBox
    evidence: Metadata
    confidence: float
    warning_ids: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        source_blob_id: str,
        page_index: int,
        kind: LayoutGroupKind,
        block_ids: tuple[str, ...],
        bounding_box: BoundingBox,
        evidence: Metadata,
        confidence: float,
        warning_ids: tuple[str, ...] = (),
    ) -> LayoutGroupHypothesis:
        normalized_box = _validated_box(bounding_box, positive_area=True)
        normalized_confidence = _validated_confidence(confidence)
        group_id = _layout_group_id(
            source_id,
            source_blob_id,
            page_index,
            kind,
            block_ids,
            normalized_box,
            evidence,
            normalized_confidence,
            warning_ids,
        )
        return cls(
            group_id=group_id,
            source_id=source_id,
            source_blob_id=source_blob_id,
            page_index=page_index,
            kind=kind,
            block_ids=block_ids,
            bounding_box=normalized_box,
            evidence=evidence,
            confidence=normalized_confidence,
            warning_ids=warning_ids,
        )

    def __post_init__(self) -> None:
        if not self.group_id:
            raise ValueError("layout group ID must be non-empty")
        if not self.source_id or not self.source_blob_id:
            raise ValueError("layout group source identity must be complete")
        if (
            isinstance(self.page_index, bool)
            or not isinstance(self.page_index, int)
            or self.page_index < 0
        ):
            raise ValueError("layout group page_index must be non-negative")
        if not isinstance(self.kind, LayoutGroupKind):
            raise ValueError("layout group kind is unsupported")
        _require_tuple("block_ids", self.block_ids)
        if not self.block_ids or len(set(self.block_ids)) != len(
            self.block_ids
        ):
            raise ValueError(
                "layout group block IDs must be non-empty and unique"
            )
        if any(not block_id for block_id in self.block_ids):
            raise ValueError("layout group block IDs must be non-empty")
        object.__setattr__(
            self,
            "bounding_box",
            _validated_box(self.bounding_box, positive_area=True),
        )
        _validate_metadata(self.evidence, required=True)
        object.__setattr__(
            self, "confidence", _validated_confidence(self.confidence)
        )
        _require_tuple("warning_ids", self.warning_ids)
        if len(set(self.warning_ids)) != len(self.warning_ids):
            raise ValueError("layout group warning IDs must be unique")
        expected_group_id = _layout_group_id(
            self.source_id,
            self.source_blob_id,
            self.page_index,
            self.kind,
            self.block_ids,
            self.bounding_box,
            self.evidence,
            self.confidence,
            self.warning_ids,
        )
        if self.group_id != expected_group_id:
            raise ValueError("layout group ID does not match its evidence")


@dataclass(frozen=True)
class PageLayoutResult:
    """A validated per-page proposal that never owns or mutates raw blocks."""

    result_id: str
    page_id: str
    source_id: str
    source_blob_id: str
    source_content_hash: str
    page_index: int
    printed_page_label: str | None
    page_width: float
    page_height: float
    coordinate_system: str
    rotation_degrees: int
    raw_blocks: tuple[LayoutBlockReference, ...]
    raw_block_ids: tuple[str, ...]
    input_text_blocks: tuple[LayoutBlockReference, ...]
    non_text_block_ids: tuple[str, ...]
    proposed_order: tuple[str, ...]
    exclusions: tuple[LayoutExclusion, ...]
    groups: tuple[LayoutGroupHypothesis, ...]
    page_kind: LayoutPageKind
    evidence: Metadata
    confidence: float
    warnings: tuple[IngestionWarning, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = LAYOUT_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source: SourceDocument,
        page: ExtractedPage,
        input_text_blocks: tuple[LayoutBlockReference, ...],
        non_text_block_ids: tuple[str, ...],
        proposed_order: tuple[str, ...],
        exclusions: tuple[LayoutExclusion, ...],
        groups: tuple[LayoutGroupHypothesis, ...],
        page_kind: LayoutPageKind,
        evidence: Metadata,
        confidence: float,
        warnings: tuple[IngestionWarning, ...],
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> PageLayoutResult:
        page_id = _source_page_id(
            source.source_id, source.blob_id, page.page_index
        )
        normalized_confidence = _validated_confidence(confidence)
        raw_blocks = tuple(
            LayoutBlockReference.from_block(block) for block in page.blocks
        )
        expected_text_blocks = tuple(
            reference for reference in raw_blocks if reference.kind == "text"
        )
        expected_non_text_ids = tuple(
            reference.block_id
            for reference in raw_blocks
            if reference.kind != "text"
        )
        if input_text_blocks != expected_text_blocks:
            raise ValueError(
                "layout text references must exactly match raw text blocks"
            )
        if non_text_block_ids != expected_non_text_ids:
            raise ValueError(
                "layout non-text IDs must exactly match raw non-text blocks"
            )
        raw_block_ids = tuple(block.block_id for block in page.blocks)
        result_id = _page_layout_result_id(
            page_id=page_id,
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            source_content_hash=source.content_hash,
            page_width=_finite_float(page.width, "page_width"),
            page_height=_finite_float(page.height, "page_height"),
            coordinate_system=page.coordinate_system,
            rotation_degrees=page.rotation_degrees,
            raw_blocks=raw_blocks,
            raw_block_ids=raw_block_ids,
            input_text_blocks=input_text_blocks,
            non_text_block_ids=non_text_block_ids,
            proposed_order=proposed_order,
            exclusions=exclusions,
            groups=groups,
            page_kind=page_kind,
            evidence=evidence,
            confidence=normalized_confidence,
            warning_ids=tuple(warning.warning_id for warning in warnings),
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )
        return cls(
            result_id=result_id,
            page_id=page_id,
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            source_content_hash=source.content_hash,
            page_index=page.page_index,
            printed_page_label=page.printed_page_label,
            page_width=page.width,
            page_height=page.height,
            coordinate_system=page.coordinate_system,
            rotation_degrees=page.rotation_degrees,
            raw_blocks=raw_blocks,
            raw_block_ids=raw_block_ids,
            input_text_blocks=input_text_blocks,
            non_text_block_ids=non_text_block_ids,
            proposed_order=proposed_order,
            exclusions=exclusions,
            groups=groups,
            page_kind=page_kind,
            evidence=evidence,
            confidence=normalized_confidence,
            warnings=warnings,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if not self.result_id or not self.page_id:
            raise ValueError("layout result identity must be complete")
        if not self.source_id or not self.source_blob_id:
            raise ValueError("layout source identity must be complete")
        _validate_sha256_source(self.source_blob_id, self.source_content_hash)
        if (
            isinstance(self.page_index, bool)
            or not isinstance(self.page_index, int)
            or self.page_index < 0
        ):
            raise ValueError("layout page_index must be non-negative")
        width = _finite_float(self.page_width, "page_width")
        height = _finite_float(self.page_height, "page_height")
        if width <= 0.0 or height <= 0.0:
            raise ValueError("layout page dimensions must be positive")
        object.__setattr__(self, "page_width", width)
        object.__setattr__(self, "page_height", height)
        if self.coordinate_system != PYMUPDF_COORDINATE_SYSTEM:
            raise ValueError(
                "layout requires the PyMuPDF unrotated crop-box coordinate "
                "system"
            )
        if (
            isinstance(self.rotation_degrees, bool)
            or not isinstance(self.rotation_degrees, int)
            or self.rotation_degrees not in (0, 90, 180, 270)
        ):
            raise ValueError("layout rotation must be 0, 90, 180, or 270")
        tuple_fields = (
            ("raw_blocks", self.raw_blocks),
            ("raw_block_ids", self.raw_block_ids),
            ("input_text_blocks", self.input_text_blocks),
            ("non_text_block_ids", self.non_text_block_ids),
            ("proposed_order", self.proposed_order),
            ("exclusions", self.exclusions),
            ("groups", self.groups),
            ("warnings", self.warnings),
        )
        for name, value in tuple_fields:
            _require_tuple(name, value)
        if tuple(
            reference.block_id for reference in self.raw_blocks
        ) != self.raw_block_ids:
            raise ValueError(
                "raw layout references and raw block IDs must agree"
            )
        if len(set(self.raw_block_ids)) != len(self.raw_block_ids):
            raise ValueError("raw layout block IDs must be unique")
        if any(not block_id for block_id in self.raw_block_ids):
            raise ValueError("raw layout block IDs must be non-empty")
        for reference in self.raw_blocks:
            for span in reference.source_spans:
                if (
                    span.source_id != self.source_id
                    or span.source_blob_id != self.source_blob_id
                    or span.page_index != self.page_index
                    or span.printed_page_label != self.printed_page_label
                ):
                    raise ValueError(
                        "raw layout spans must refer to the exact source page"
                    )
                if span.bounding_box is not None:
                    x0, y0, x1, y1 = span.bounding_box
                    if x0 < 0.0 or y0 < 0.0 or x1 > width or y1 > height:
                        raise ValueError(
                            "raw layout span lies outside the page"
                        )
        expected_text_blocks = tuple(
            reference
            for reference in self.raw_blocks
            if reference.kind == "text"
        )
        if self.input_text_blocks != expected_text_blocks:
            raise ValueError(
                "layout text references must exactly match raw text blocks"
            )
        expected_non_text_ids = tuple(
            reference.block_id
            for reference in self.raw_blocks
            if reference.kind != "text"
        )
        if self.non_text_block_ids != expected_non_text_ids:
            raise ValueError(
                "layout non-text IDs must exactly match raw non-text blocks"
            )
        text_ids = tuple(
            reference.block_id for reference in self.input_text_blocks
        )
        if len(set(text_ids)) != len(text_ids):
            raise ValueError("layout text block references must be unique")
        if any(block_id not in self.raw_block_ids for block_id in text_ids):
            raise ValueError(
                "layout text references must resolve to raw block IDs"
            )
        if len(set(self.non_text_block_ids)) != len(self.non_text_block_ids):
            raise ValueError("non-text layout block IDs must be unique")
        if set(text_ids).intersection(self.non_text_block_ids):
            raise ValueError(
                "text and non-text layout block IDs must be disjoint"
            )
        if set(text_ids).union(self.non_text_block_ids) != set(
            self.raw_block_ids
        ):
            raise ValueError(
                "layout inputs must account for every raw page block"
            )
        text_id_set = set(text_ids)
        if (
            tuple(
                block_id
                for block_id in self.raw_block_ids
                if block_id in text_id_set
            )
            != text_ids
        ):
            raise ValueError(
                "layout text references must retain native raw order"
            )
        if (
            tuple(
                block_id
                for block_id in self.raw_block_ids
                if block_id not in text_id_set
            )
            != self.non_text_block_ids
        ):
            raise ValueError("layout non-text IDs must retain native raw order")
        for reference in self.input_text_blocks:
            for span in reference.source_spans:
                if (
                    span.source_id != self.source_id
                    or span.source_blob_id != self.source_blob_id
                    or span.page_index != self.page_index
                ):
                    raise ValueError(
                        "layout text spans must refer to the exact source page"
                    )
                if span.printed_page_label != self.printed_page_label:
                    raise ValueError(
                        "layout span labels must match the source page label"
                    )
                if span.bounding_box is not None:
                    x0, y0, x1, y1 = span.bounding_box
                    if x0 < 0.0 or y0 < 0.0 or x1 > width or y1 > height:
                        raise ValueError(
                            "layout source span lies outside the page"
                        )
        if len(set(self.proposed_order)) != len(self.proposed_order):
            raise ValueError("proposed layout order must contain unique IDs")
        exclusion_ids = tuple(
            exclusion.block_id for exclusion in self.exclusions
        )
        if len(set(exclusion_ids)) != len(exclusion_ids):
            raise ValueError("layout exclusions must contain unique block IDs")
        if set(self.proposed_order).intersection(exclusion_ids):
            raise ValueError(
                "ordered and excluded layout blocks must be disjoint"
            )
        if set(self.proposed_order).union(exclusion_ids) != set(text_ids):
            raise ValueError(
                "layout order and documented exclusions must cover all "
                "text blocks"
            )
        references_by_id = {
            reference.block_id: reference
            for reference in self.input_text_blocks
        }
        group_ids = tuple(group.group_id for group in self.groups)
        if len(set(group_ids)) != len(group_ids):
            raise ValueError("layout group IDs must be unique")
        membership: list[str] = []
        warning_ids = tuple(warning.warning_id for warning in self.warnings)
        if len(set(warning_ids)) != len(warning_ids):
            raise ValueError("layout warning IDs must be unique")
        allowed_warning_objects = set(text_ids).union(group_ids)
        for warning in self.warnings:
            _require_tuple("warning object_ids", warning.object_ids)
            _require_tuple("warning source_spans", warning.source_spans)
            _validate_metadata(warning.evidence, required=False)
            if any(
                object_id not in allowed_warning_objects
                for object_id in warning.object_ids
            ):
                raise ValueError(
                    "layout warning object IDs must resolve in the result"
                )
            for span in warning.source_spans:
                _validate_result_span(self, span)
            expected_warning_id = stable_id(
                "warning",
                warning.code,
                warning.object_ids,
                tuple(span.identity_parts() for span in warning.source_spans),
                warning.evidence,
            )
            if warning.warning_id != expected_warning_id:
                raise ValueError(
                    "layout warning ID does not match its evidence"
                )
        for group in self.groups:
            if (
                group.source_id != self.source_id
                or group.source_blob_id != self.source_blob_id
                or group.page_index != self.page_index
            ):
                raise ValueError(
                    "layout groups must refer to the exact source page"
                )
            if any(
                block_id not in self.proposed_order
                for block_id in group.block_ids
            ):
                raise ValueError(
                    "layout groups may contain only ordered text blocks"
                )
            if (
                tuple(
                    block_id
                    for block_id in self.proposed_order
                    if block_id in set(group.block_ids)
                )
                != group.block_ids
            ):
                raise ValueError(
                    "layout group block IDs must follow proposed order"
                )
            membership.extend(group.block_ids)
            expected_box = _union_box(
                tuple(
                    _required_reference_box(references_by_id[block_id])
                    for block_id in group.block_ids
                )
            )
            if group.bounding_box != expected_box:
                raise ValueError(
                    "layout group box must enclose its referenced blocks"
                )
            if any(
                warning_id not in warning_ids
                for warning_id in group.warning_ids
            ):
                raise ValueError("layout group warning IDs must resolve")
            warnings_by_id = {
                warning.warning_id: warning for warning in self.warnings
            }
            for warning_id in group.warning_ids:
                warning = warnings_by_id[warning_id]
                if (
                    group.group_id not in warning.object_ids
                    and not set(group.block_ids).intersection(
                        warning.object_ids
                    )
                ):
                    raise ValueError(
                        "layout group warnings must target the group or a "
                        "member block"
                    )
            expected_group_id = _layout_group_id(
                self.source_id,
                self.source_blob_id,
                self.page_index,
                group.kind,
                group.block_ids,
                group.bounding_box,
                group.evidence,
                group.confidence,
                group.warning_ids,
            )
            if group.group_id != expected_group_id:
                raise ValueError("layout group ID does not match its evidence")
        if len(membership) != len(set(membership)) or set(membership) != set(
            self.proposed_order
        ):
            raise ValueError(
                "every ordered text block must belong to one group"
            )
        if not isinstance(self.page_kind, LayoutPageKind):
            raise ValueError("layout page kind is unsupported")
        if self.page_kind is LayoutPageKind.EMPTY:
            if self.input_text_blocks or self.exclusions:
                raise ValueError(
                    "an empty layout cannot contain text references"
                )
            if self.proposed_order or self.groups:
                raise ValueError(
                    "an empty layout cannot contain ordered groups"
                )
        elif self.page_kind is LayoutPageKind.AMBIGUOUS:
            if not self.proposed_order and not self.exclusions:
                raise ValueError(
                    "an ambiguous layout must contain ordered or excluded text"
                )
            if bool(self.proposed_order) != bool(self.groups):
                raise ValueError(
                    "ambiguous ordered blocks and groups must be present "
                    "together"
                )
        elif not self.proposed_order or not self.groups:
            raise ValueError("a non-empty layout must contain ordered groups")
        if self.page_kind is LayoutPageKind.AMBIGUOUS and not self.warnings:
            raise ValueError("an ambiguous layout must include a warning")
        explicitly_warned_kinds = (
            LayoutGroupKind.FOOTNOTE_CANDIDATE,
            LayoutGroupKind.SIDEBAR,
            LayoutGroupKind.UNCERTAIN,
        )
        if any(
            group.kind in explicitly_warned_kinds and not group.warning_ids
            for group in self.groups
        ):
            raise ValueError(
                "uncertain layout groups and candidates must link to an "
                "explicit warning"
            )
        _validate_metadata(self.evidence, required=True)
        object.__setattr__(
            self, "confidence", _validated_confidence(self.confidence)
        )
        identity_fields = (
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        if any(not value for value in identity_fields):
            raise ValueError("layout processor identity must be complete")
        if self.contract_version != LAYOUT_CONTRACT_VERSION:
            raise ValueError("unsupported layout contract version")
        expected_page_id = _source_page_id(
            self.source_id, self.source_blob_id, self.page_index
        )
        if self.page_id != expected_page_id:
            raise ValueError(
                "layout page ID does not match its source identity"
            )
        expected_result_id = _page_layout_result_id(
            page_id=self.page_id,
            source_id=self.source_id,
            source_blob_id=self.source_blob_id,
            source_content_hash=self.source_content_hash,
            page_width=width,
            page_height=height,
            coordinate_system=self.coordinate_system,
            rotation_degrees=self.rotation_degrees,
            raw_blocks=self.raw_blocks,
            raw_block_ids=self.raw_block_ids,
            input_text_blocks=self.input_text_blocks,
            non_text_block_ids=self.non_text_block_ids,
            proposed_order=self.proposed_order,
            exclusions=self.exclusions,
            groups=self.groups,
            page_kind=self.page_kind,
            evidence=self.evidence,
            confidence=self.confidence,
            warning_ids=warning_ids,
            processor_name=self.processor_name,
            processor_version=self.processor_version,
            configuration_digest=self.configuration_digest,
        )
        if self.result_id != expected_result_id:
            raise ValueError("layout result ID does not match its evidence")


@dataclass(frozen=True)
class _Item:
    reference: LayoutBlockReference
    box: BoundingBox


class DeterministicLayoutProcessor(BasePageLayoutProcessor):
    """Propose bounded page-local text order from transparent geometry only."""

    name = "deterministic-page-layout"
    version = "2"

    def __init__(
        self, configuration: LayoutConfiguration | None = None
    ) -> None:
        self.configuration = configuration or LayoutConfiguration()

    @property
    def configuration_digest(self) -> str:
        return self.configuration.configuration_digest

    def analyze(
        self, document: ExtractedDocument
    ) -> tuple[PageLayoutResult, ...]:
        return tuple(
            self.analyze_page(document.source, page) for page in document.pages
        )

    def analyze_page(
        self, source: SourceDocument, page: ExtractedPage
    ) -> PageLayoutResult:
        self._preflight_page(source, page)
        self._validate_source_page(source, page)
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

        warnings: list[IngestionWarning] = []
        if exclusions:
            warnings.append(
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
                        exclusion.block_id for exclusion in exclusions
                    ),
                    evidence=(("excluded_count", str(len(exclusions))),),
                )
            )
        if not items:
            has_text = bool(references)
            return PageLayoutResult.create(
                source=source,
                page=page,
                input_text_blocks=references,
                non_text_block_ids=non_text_ids,
                proposed_order=(),
                exclusions=tuple(exclusions),
                groups=(),
                page_kind=(
                    LayoutPageKind.AMBIGUOUS
                    if has_text
                    else LayoutPageKind.EMPTY
                ),
                evidence=(
                    ("algorithm", "bounded_geometry_v2"),
                    ("analyzable_text_block_count", "0"),
                    ("unanalysable_text_block_count", str(len(exclusions))),
                    ("non_text_block_count", str(len(non_text_ids))),
                ),
                confidence=0.0 if has_text else 1.0,
                warnings=tuple(warnings),
                processor_name=self.name,
                processor_version=self.version,
                configuration_digest=self.configuration_digest,
            )

        if page.rotation_degrees != 0:
            warning = self._warning(
                source,
                page,
                code="layout.rotated_page_ambiguous",
                message=(
                    "Nonzero page rotation lacks verified display-space "
                    "reading-order semantics"
                ),
                items=tuple(items),
                object_ids=tuple(
                    item.reference.block_id for item in items
                ),
                evidence=(
                    ("rotation_degrees", str(page.rotation_degrees)),
                    ("ordering", "unrotated_geometry_fallback"),
                ),
            )
            warnings.append(warning)
            return self._ambiguous_result(
                source,
                page,
                references,
                non_text_ids,
                items,
                exclusions,
                warnings,
                evidence=(
                    ("algorithm", "bounded_geometry_v2"),
                    ("ambiguity", "nonzero_page_rotation"),
                    ("rotation_degrees", str(page.rotation_degrees)),
                ),
            )

        overlap_pairs = self._overlap_pairs(items)
        if overlap_pairs:
            warning = self._warning(
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
            warnings.append(warning)
            return self._ambiguous_result(
                source,
                page,
                references,
                non_text_ids,
                items,
                exclusions,
                warnings,
                evidence=(
                    ("algorithm", "bounded_geometry_v2"),
                    ("ambiguity", "overlapping_text_boxes"),
                    ("overlap_pair_count", str(overlap_pairs)),
                ),
            )

        bottom_text, flow = self._split_bottom_text(items, page.height)
        bottom_warning_ids: tuple[str, ...] = ()
        if bottom_text:
            warning = self._warning(
                source,
                page,
                code="layout.separated_bottom_text_ambiguous",
                message=(
                    "Separated bottom text may be a footnote, footer, or "
                    "final sparse paragraph"
                ),
                items=tuple(bottom_text),
                object_ids=tuple(
                    item.reference.block_id for item in bottom_text
                ),
                evidence=(
                    ("hypothesis", "footnote_candidate"),
                    ("semantic_role", "unverified"),
                ),
            )
            warnings.append(warning)
            bottom_warning_ids = (warning.warning_id,)
        wide, narrow = self._split_wide(flow, page.width)
        split = self._best_column_split(narrow, page.width, page.height)
        if split is None:
            separated = self._separated_group_conflict(flow, page.width)
            if separated:
                warning = self._warning(
                    source,
                    page,
                    code="layout.discontinuous_side_groups_ambiguous",
                    message=(
                        "Separated horizontal groups lack sufficient actual "
                        "vertical flow concurrency"
                    ),
                    items=tuple(items),
                    object_ids=tuple(
                        item.reference.block_id for item in items
                    ),
                    evidence=(
                        ("candidate_split_count", str(separated)),
                        ("column_support", "insufficient"),
                    ),
                )
                warnings.append(warning)
                return self._ambiguous_result(
                    source,
                    page,
                    references,
                    non_text_ids,
                    items,
                    exclusions,
                    warnings,
                    evidence=(
                        ("algorithm", "bounded_geometry_v2"),
                        ("ambiguity", "discontinuous_side_groups"),
                    ),
                )
            bridging = self._bridging_conflict(flow, page.width, page.height)
            if bridging:
                warning = self._warning(
                    source,
                    page,
                    code="layout.bridging_block_ambiguous",
                    message=(
                        "A top block bridges concurrent side groups without "
                        "sufficient spanning-heading evidence"
                    ),
                    items=tuple(items),
                    object_ids=tuple(
                        item.reference.block_id for item in items
                    ),
                    evidence=(("bridging_block_count", str(bridging)),),
                )
                warnings.append(warning)
                return self._ambiguous_result(
                    source,
                    page,
                    references,
                    non_text_ids,
                    items,
                    exclusions,
                    warnings,
                    evidence=(
                        ("algorithm", "bounded_geometry_v2"),
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
                    source,
                    page,
                    bottom_text,
                    bottom_warning_ids,
                )
            )
            order = tuple(
                item.reference.block_id
                for item in [
                    *ordered_flow,
                    *sorted(bottom_text, key=_geometric_key),
                ]
            )
            return PageLayoutResult.create(
                source=source,
                page=page,
                input_text_blocks=references,
                non_text_block_ids=non_text_ids,
                proposed_order=order,
                exclusions=tuple(exclusions),
                groups=tuple(groups),
                page_kind=(
                    LayoutPageKind.AMBIGUOUS
                    if bottom_text
                    else LayoutPageKind.ONE_COLUMN
                ),
                evidence=(
                    ("algorithm", "bounded_geometry_v2"),
                    ("column_count", "1"),
                    ("bottom_text_block_count", str(len(bottom_text))),
                    ("non_text_block_count", str(len(non_text_ids))),
                ),
                confidence=(
                    0.35
                    if bottom_text
                    else (0.90 if not exclusions else 0.70)
                ),
                warnings=tuple(warnings),
                processor_name=self.name,
                processor_version=self.version,
                configuration_digest=self.configuration_digest,
            )

        left, right, gap, overlap_ratio = split
        if gap < self.configuration.minimum_column_gap_ratio * page.width:
            warning = self._warning(
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
                    (
                        "minimum_column_gap_points",
                        _number(
                            self.configuration.minimum_column_gap_ratio
                            * page.width
                        ),
                    ),
                ),
            )
            warnings.append(warning)
            return self._ambiguous_result(
                source,
                page,
                references,
                non_text_ids,
                items,
                exclusions,
                warnings,
                evidence=(
                    ("algorithm", "bounded_geometry_v2"),
                    ("ambiguity", "weak_column_separation"),
                    ("column_gap_points", _number(gap)),
                ),
            )

        left_nested_split = self._best_column_split(
            left, page.width, page.height
        )
        right_nested_split = self._best_column_split(
            right, page.width, page.height
        )
        minimum_gap = (
            self.configuration.minimum_column_gap_ratio * page.width
        )
        if any(
            nested_split is not None and nested_split[2] >= minimum_gap
            for nested_split in (left_nested_split, right_nested_split)
        ):
            warning = self._warning(
                source,
                page,
                code="layout.multiple_column_groups_ambiguous",
                message=(
                    "More than two concurrent horizontal groups exceed the "
                    "processor's confident column model"
                ),
                items=tuple(items),
                object_ids=tuple(
                    item.reference.block_id for item in items
                ),
                evidence=(("supported_confident_column_count", "2"),),
            )
            warnings.append(warning)
            return self._ambiguous_result(
                source,
                page,
                references,
                non_text_ids,
                items,
                exclusions,
                warnings,
                evidence=(
                    ("algorithm", "bounded_geometry_v2"),
                    ("ambiguity", "more_than_two_column_groups"),
                ),
            )

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
        unsupported_wide = [item for item in wide if item not in spanning]
        if unsupported_wide or len(spanning) > 1:
            warning = self._warning(
                source,
                page,
                code="layout.spanning_position_ambiguous",
                message=(
                    "Wide text crosses candidate columns away from the "
                    "supported heading position"
                ),
                items=tuple(
                    [*unsupported_wide, *spanning]
                    if len(spanning) > 1
                    else unsupported_wide
                ),
                object_ids=tuple(
                    item.reference.block_id
                    for item in (
                        [*unsupported_wide, *spanning]
                        if len(spanning) > 1
                        else unsupported_wide
                    )
                ),
                evidence=(
                    ("unsupported_wide_count", str(len(unsupported_wide))),
                    ("spanning_candidate_count", str(len(spanning))),
                ),
            )
            warnings.append(warning)
            return self._ambiguous_result(
                source,
                page,
                references,
                non_text_ids,
                items,
                exclusions,
                warnings,
                evidence=(
                    ("algorithm", "bounded_geometry_v2"),
                    ("ambiguity", "unsupported_spanning_position"),
                ),
            )

        left_width = max(item.box[2] for item in left) - min(
            item.box[0] for item in left
        )
        right_width = max(item.box[2] for item in right) - min(
            item.box[0] for item in right
        )
        width_balance = min(left_width, right_width) / max(
            left_width, right_width
        )
        sidebar = (
            width_balance < self.configuration.balanced_column_width_ratio
            and min(left_width, right_width) / page.width
            < self.configuration.sidebar_width_ratio
        )
        sorted_spanning = sorted(spanning, key=_geometric_key)
        sorted_bottom_text = sorted(bottom_text, key=_geometric_key)
        if sidebar:
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
                object_ids=tuple(
                    item.reference.block_id for item in sidebar_items
                ),
                evidence=(
                    ("column_width_balance", _number(width_balance)),
                    (
                        "narrow_width_points",
                        _number(min(left_width, right_width)),
                    ),
                ),
            )
            warnings.append(warning)
            warning_ids = (warning.warning_id,)
            middle = sorted([*main_items, *sidebar_items], key=_geometric_key)
            groups = []
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
                    warning_ids,
                )
            )
            groups.extend(
                self._bottom_text_groups(
                    source,
                    page,
                    bottom_text,
                    bottom_warning_ids,
                )
            )
            order_items = [*sorted_spanning, *middle, *sorted_bottom_text]
            return PageLayoutResult.create(
                source=source,
                page=page,
                input_text_blocks=references,
                non_text_block_ids=non_text_ids,
                proposed_order=tuple(
                    item.reference.block_id for item in order_items
                ),
                exclusions=tuple(exclusions),
                groups=tuple(groups),
                page_kind=LayoutPageKind.AMBIGUOUS,
                evidence=(
                    ("algorithm", "bounded_geometry_v2"),
                    ("hypothesis", "main_flow_with_sidebar"),
                    ("ordering", "geometric_and_explicitly_uncertain"),
                    ("column_gap_points", _number(gap)),
                ),
                confidence=0.35,
                warnings=tuple(warnings),
                processor_name=self.name,
                processor_version=self.version,
                configuration_digest=self.configuration_digest,
            )

        sorted_left = sorted(left, key=_geometric_key)
        sorted_right = sorted(right, key=_geometric_key)
        confidence = min(0.95, 0.72 + gap / page.width)
        groups = []
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
                source,
                page,
                bottom_text,
                bottom_warning_ids,
            )
        )
        order_items = [
            *sorted_spanning,
            *sorted_left,
            *sorted_right,
            *sorted_bottom_text,
        ]
        return PageLayoutResult.create(
            source=source,
            page=page,
            input_text_blocks=references,
            non_text_block_ids=non_text_ids,
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
                ("algorithm", "bounded_geometry_v2"),
                ("column_count", "2"),
                ("column_gap_points", _number(gap)),
                ("vertical_overlap_ratio", _number(overlap_ratio)),
                ("bottom_text_block_count", str(len(bottom_text))),
                ("non_text_block_count", str(len(non_text_ids))),
            ),
            confidence=(
                0.35
                if bottom_text
                else (
                    confidence
                    if not exclusions
                    else min(confidence, 0.70)
                )
            ),
            warnings=tuple(warnings),
            processor_name=self.name,
            processor_version=self.version,
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
                count_identity(
                    span.source_blob_id, "span.source_blob_id"
                )
                count_identity(
                    span.source_object_id, "span.source_object_id"
                )
                count_identity(
                    span.printed_page_label,
                    "span.printed_page_label",
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

    def _separated_group_conflict(
        self, items: list[_Item], page_width: float
    ) -> int:
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
            split = self._best_column_split(
                remaining, page_width, page_height
            )
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
            overlap_ratio = self._column_support(
                left, right, page_height
            )
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
        ordered_ids = {
            item.reference.block_id for item in ordered
        }
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
        return PageLayoutResult.create(
            source=source,
            page=page,
            input_text_blocks=references,
            non_text_block_ids=non_text_ids,
            proposed_order=tuple(item.reference.block_id for item in ordered),
            exclusions=tuple(exclusions),
            groups=(group,),
            page_kind=LayoutPageKind.AMBIGUOUS,
            evidence=evidence,
            confidence=0.25,
            warnings=tuple(warnings),
            processor_name=self.name,
            processor_version=self.version,
            configuration_digest=self.configuration_digest,
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
        items: list[_Item],
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


def _source_page_id(
    source_id: str, source_blob_id: str, page_index: int
) -> str:
    return stable_id("source-page", source_id, source_blob_id, page_index)


def _layout_group_id(
    source_id: str,
    source_blob_id: str,
    page_index: int,
    kind: LayoutGroupKind,
    block_ids: tuple[str, ...],
    bounding_box: BoundingBox,
    evidence: Metadata,
    confidence: float,
    warning_ids: tuple[str, ...],
) -> str:
    return stable_id(
        "layout-group",
        source_id,
        source_blob_id,
        page_index,
        kind.value,
        block_ids,
        bounding_box,
        evidence,
        confidence,
        warning_ids,
    )


def _page_layout_result_id(
    *,
    page_id: str,
    source_id: str,
    source_blob_id: str,
    source_content_hash: str,
    page_width: float,
    page_height: float,
    coordinate_system: str,
    rotation_degrees: int,
    raw_blocks: tuple[LayoutBlockReference, ...],
    raw_block_ids: tuple[str, ...],
    input_text_blocks: tuple[LayoutBlockReference, ...],
    non_text_block_ids: tuple[str, ...],
    proposed_order: tuple[str, ...],
    exclusions: tuple[LayoutExclusion, ...],
    groups: tuple[LayoutGroupHypothesis, ...],
    page_kind: LayoutPageKind,
    evidence: Metadata,
    confidence: float,
    warning_ids: tuple[str, ...],
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "page-layout-result",
        LAYOUT_CONTRACT_VERSION,
        page_id,
        source_id,
        source_blob_id,
        source_content_hash,
        page_width,
        page_height,
        coordinate_system,
        rotation_degrees,
        tuple(reference.identity_parts() for reference in raw_blocks),
        raw_block_ids,
        tuple(reference.identity_parts() for reference in input_text_blocks),
        non_text_block_ids,
        proposed_order,
        tuple(exclusion.identity_parts() for exclusion in exclusions),
        tuple(group.group_id for group in groups),
        page_kind.value,
        evidence,
        confidence,
        warning_ids,
        processor_name,
        processor_version,
        configuration_digest,
    )


def _normalized_span(span: SourceSpan) -> SourceSpan:
    if not isinstance(span, SourceSpan):
        raise TypeError("layout source spans must be SourceSpan values")
    box = (
        _validated_box(span.bounding_box, positive_area=False)
        if span.bounding_box is not None
        else None
    )
    return SourceSpan(
        source_id=span.source_id,
        source_blob_id=span.source_blob_id,
        page_index=span.page_index,
        printed_page_label=span.printed_page_label,
        source_object_id=span.source_object_id,
        bounding_box=box,
        start_offset=span.start_offset,
        end_offset=span.end_offset,
    )


def _validated_box(box: BoundingBox, *, positive_area: bool) -> BoundingBox:
    if not isinstance(box, tuple) or len(box) != 4:
        raise ValueError("layout bounding boxes must contain four coordinates")
    values = tuple(
        _finite_float(value, "bounding box coordinate") for value in box
    )
    x0, y0, x1, y1 = values
    if x1 < x0 or y1 < y0 or (positive_area and (x1 <= x0 or y1 <= y0)):
        raise ValueError("layout bounding boxes must have ordered geometry")
    return (x0, y0, x1, y1)


def _finite_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a finite number")
    try:
        normalized = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be a finite number")
    return 0.0 if normalized == 0.0 else normalized


def _union_box(boxes: tuple[BoundingBox, ...]) -> BoundingBox:
    if not boxes:
        raise ValueError("cannot compute a layout box without source boxes")
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _required_reference_box(reference: LayoutBlockReference) -> BoundingBox:
    box = reference.bounding_box
    if box is None or box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError("ordered layout references require positive geometry")
    return box


def _validate_metadata(metadata: Metadata, *, required: bool) -> None:
    _require_tuple("evidence", metadata)
    if required and not metadata:
        raise ValueError("layout evidence must be non-empty")
    keys: list[str] = []
    for entry in metadata:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ValueError("layout evidence entries must be key/value tuples")
        key, value = entry
        if not isinstance(key, str) or not key or not isinstance(value, str):
            raise ValueError(
                "layout evidence must contain string keys and values"
            )
        keys.append(key)
    if len(keys) != len(set(keys)):
        raise ValueError("layout evidence keys must be unique")


def _validated_confidence(confidence: float) -> float:
    if isinstance(confidence, bool) or not isinstance(confidence, int | float):
        raise ValueError("layout confidence must be a finite bounded score")
    normalized = float(confidence)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError("layout confidence must be between zero and one")
    return normalized


def _validate_sha256_source(source_blob_id: str, source_hash: str) -> None:
    if len(source_hash) != 64:
        raise ValueError("layout source hash must be a SHA-256 digest")
    try:
        int(source_hash, 16)
    except ValueError as error:
        raise ValueError(
            "layout source hash must be a SHA-256 digest"
        ) from error
    if source_blob_id != f"blob:sha256:{source_hash}":
        raise ValueError("layout source blob and hash must agree")


def _validate_result_span(result: PageLayoutResult, span: SourceSpan) -> None:
    normalized = _normalized_span(span)
    if (
        normalized.source_id != result.source_id
        or normalized.source_blob_id != result.source_blob_id
        or normalized.page_index != result.page_index
        or normalized.printed_page_label != result.printed_page_label
    ):
        raise ValueError(
            "layout warning span must refer to the exact source page"
        )
    if normalized.bounding_box is not None:
        x0, y0, x1, y1 = normalized.bounding_box
        if (
            x0 < 0.0
            or y0 < 0.0
            or x1 > result.page_width
            or y1 > result.page_height
        ):
            raise ValueError("layout warning span lies outside the page")


def _require_tuple(name: str, value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be an immutable tuple")


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

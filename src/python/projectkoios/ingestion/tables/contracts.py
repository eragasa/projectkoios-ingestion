"""Contracts and deterministic facades for table detection."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, BinaryIO, Protocol, cast

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout import (
    DeterministicLayoutProcessor,
    PageLayoutResult,
)
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedBlock,
    ExtractedDocument,
    IngestionWarning,
    Metadata,
    SourceDocument,
    SourceSpan,
)
from projectkoios.ingestion.pdf.models import (
    PYMUPDF_COORDINATE_SYSTEM,
    PageRegionSelection,
    RenderedRegion,
)
from projectkoios.ingestion.pdf.renderer import PyMuPdfRegionRenderer

TABLE_CONTRACT_VERSION = "1.0"
TABLE_DETECTOR_VERSION = "1"
TABLE_RULE_INSPECTOR_VERSION = "1"
_MAX_SOURCE_BYTES = 1_000_000_000
_MAX_PAGES = 512
_MAX_INPUT_BLOCKS = 16_384
_MAX_TEXT_BLOCKS = 8_192
_MAX_TEXT_CHARACTERS = 5_000_000
_MAX_SOURCE_SPANS = 16_384
_MAX_BACKEND_DRAWINGS_PER_PAGE = 2_000_000
_MAX_BACKEND_DRAWING_ITEMS_PER_PAGE = 10_000_000
_MAX_DRAWINGS_PER_PAGE = 100_000
_MAX_DRAWING_ITEMS_PER_PAGE = 500_000
_MAX_RULE_SEGMENTS_PER_PAGE = 100_000
_MAX_TOTAL_RULE_SEGMENTS = 200_000
_MAX_CANDIDATES = 256
_MAX_REGIONS_PER_CANDIDATE = 64
_MAX_BLOCKS_PER_REGION = 2_048
_MAX_ASSOCIATIONS_PER_CANDIDATE = 256
_MAX_WARNINGS = 4_096
_MAX_RESULT_BYTES = 128_000_000
_MAX_TOTAL_RENDERED_PNG_BYTES = 100_000_000
_MAX_TOTAL_RENDERED_PIXELS = 100_000_000
_MAX_IDENTITY_CHARACTERS = 4_096
_MAX_TEXT_FIELD_CHARACTERS = 65_536
_MAX_METADATA_CHARACTERS = 100_000
_TABLE_TITLE = re.compile(
    r"^\s*Table(?:\s+(?P<label>(?:[A-Za-z]?\d+(?:[.\-]\d+)*"
    r"|[IVXLCDM]+|[A-Za-z])))?\b",
    re.IGNORECASE,
)
_CONTINUED = re.compile(r"\bcontinued\b", re.IGNORECASE)
_CAPTION = re.compile(r"^\s*Caption\s*[:.]", re.IGNORECASE)
_NOTE = re.compile(r"^\s*(?:Note|Notes|Source)\s*[:.]", re.IGNORECASE)


class _PageLayoutProcessor(Protocol):
    def analyze(
        self, document: ExtractedDocument
    ) -> tuple[PageLayoutResult, ...]: ...


class _PageRegionRenderer(Protocol):
    def render(
        self,
        source: SourceDocument,
        content: BinaryIO,
        selections: Iterable[PageRegionSelection],
    ) -> tuple[RenderedRegion, ...]: ...


class _TableRuleInspector(Protocol):
    name: str
    version: str

    def inspect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
        configuration: TableDetectionConfiguration,
    ) -> tuple[TablePageRuleEvidence, ...]: ...


class TableDetectionLimitError(ValueError):
    """Raised before table detection exceeds a configured hard bound."""


class TableRuleOrientation(StrEnum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class TableBoundaryKind(StrEnum):
    RULED = "ruled"
    UNRULED = "unruled"
    MIXED = "mixed"


class TableEvidenceStatus(StrEnum):
    """Detection status with no accepted or validated state."""

    PROPOSED = "proposed"
    AMBIGUOUS = "ambiguous"


class TableAssociationRole(StrEnum):
    TITLE = "title"
    CAPTION = "caption"
    NOTE = "note"
    CONTINUATION_LABEL = "continuation_label"


@dataclass(frozen=True)
class TableDetectionConfiguration:
    max_source_bytes: int = _MAX_SOURCE_BYTES
    max_pages: int = _MAX_PAGES
    max_input_blocks: int = _MAX_INPUT_BLOCKS
    max_text_blocks: int = _MAX_TEXT_BLOCKS
    max_text_characters: int = _MAX_TEXT_CHARACTERS
    max_source_spans: int = _MAX_SOURCE_SPANS
    max_backend_drawings_per_page: int = _MAX_BACKEND_DRAWINGS_PER_PAGE
    max_backend_drawing_items_per_page: int = (
        _MAX_BACKEND_DRAWING_ITEMS_PER_PAGE
    )
    max_drawings_per_page: int = _MAX_DRAWINGS_PER_PAGE
    max_drawing_items_per_page: int = _MAX_DRAWING_ITEMS_PER_PAGE
    max_rule_segments_per_page: int = _MAX_RULE_SEGMENTS_PER_PAGE
    max_total_rule_segments: int = _MAX_TOTAL_RULE_SEGMENTS
    max_candidates: int = _MAX_CANDIDATES
    max_regions_per_candidate: int = _MAX_REGIONS_PER_CANDIDATE
    max_blocks_per_region: int = _MAX_BLOCKS_PER_REGION
    max_associations_per_candidate: int = _MAX_ASSOCIATIONS_PER_CANDIDATE
    max_warnings: int = _MAX_WARNINGS
    max_result_bytes: int = _MAX_RESULT_BYTES
    max_total_rendered_png_bytes: int = _MAX_TOTAL_RENDERED_PNG_BYTES
    max_total_rendered_pixels: int = _MAX_TOTAL_RENDERED_PIXELS
    minimum_rows: int = 2
    minimum_columns: int = 2
    row_alignment_tolerance_points: float = 18.0
    column_alignment_tolerance_points: float = 24.0
    maximum_row_gap_points: float = 96.0
    association_distance_points: float = 72.0
    rule_proximity_points: float = 24.0
    render_padding_points: float = 6.0
    proposed_confidence_threshold: float = 0.70
    prose_character_threshold: int = 240

    def __post_init__(self) -> None:
        integer_limits = (
            ("max_source_bytes", _MAX_SOURCE_BYTES),
            ("max_pages", _MAX_PAGES),
            ("max_input_blocks", _MAX_INPUT_BLOCKS),
            ("max_text_blocks", _MAX_TEXT_BLOCKS),
            ("max_text_characters", _MAX_TEXT_CHARACTERS),
            ("max_source_spans", _MAX_SOURCE_SPANS),
            (
                "max_backend_drawings_per_page",
                _MAX_BACKEND_DRAWINGS_PER_PAGE,
            ),
            (
                "max_backend_drawing_items_per_page",
                _MAX_BACKEND_DRAWING_ITEMS_PER_PAGE,
            ),
            ("max_drawings_per_page", _MAX_DRAWINGS_PER_PAGE),
            ("max_drawing_items_per_page", _MAX_DRAWING_ITEMS_PER_PAGE),
            ("max_rule_segments_per_page", _MAX_RULE_SEGMENTS_PER_PAGE),
            ("max_total_rule_segments", _MAX_TOTAL_RULE_SEGMENTS),
            ("max_candidates", _MAX_CANDIDATES),
            ("max_regions_per_candidate", _MAX_REGIONS_PER_CANDIDATE),
            ("max_blocks_per_region", _MAX_BLOCKS_PER_REGION),
            (
                "max_associations_per_candidate",
                _MAX_ASSOCIATIONS_PER_CANDIDATE,
            ),
            ("max_warnings", _MAX_WARNINGS),
            ("max_result_bytes", _MAX_RESULT_BYTES),
            (
                "max_total_rendered_png_bytes",
                _MAX_TOTAL_RENDERED_PNG_BYTES,
            ),
            ("max_total_rendered_pixels", _MAX_TOTAL_RENDERED_PIXELS),
            ("minimum_rows", 128),
            ("minimum_columns", 128),
            ("prose_character_threshold", _MAX_TEXT_FIELD_CHARACTERS),
        )
        for name, hard_maximum in integer_limits:
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer")
            if value > hard_maximum:
                raise TableDetectionLimitError(
                    f"{name} exceeds its implementation maximum "
                    f"({hard_maximum})"
                )
        for name, upper in (
            ("row_alignment_tolerance_points", 144.0),
            ("column_alignment_tolerance_points", 144.0),
            ("maximum_row_gap_points", 720.0),
            ("association_distance_points", 720.0),
            ("rule_proximity_points", 144.0),
            ("render_padding_points", 72.0),
        ):
            value = _finite_float(name, getattr(self, name))
            if value < 0.0 or value > upper:
                raise ValueError(f"{name} must be between zero and {upper}")
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "proposed_confidence_threshold",
            _unit_float(
                "proposed_confidence_threshold",
                self.proposed_confidence_threshold,
            ),
        )

    @property
    def configuration_digest(self) -> str:
        return stable_id("table-detection-configuration", self.identity_parts())

    def identity_parts(self) -> tuple[object, ...]:
        return tuple(
            (name, getattr(self, name)) for name in self.__dataclass_fields__
        )


@dataclass(frozen=True)
class TableRuleSegment:
    segment_id: str
    source_id: str
    source_blob_id: str
    page_index: int
    orientation: TableRuleOrientation
    start: tuple[float, float]
    end: tuple[float, float]
    stroke_width: float
    source_object_id: str
    contract_version: str = TABLE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source: SourceDocument,
        page_index: int,
        orientation: TableRuleOrientation,
        start: tuple[float, float],
        end: tuple[float, float],
        stroke_width: float,
        source_object_id: str,
    ) -> TableRuleSegment:
        normalized_start, normalized_end, width = _validate_rule_parts(
            source.source_id,
            source.blob_id,
            page_index,
            orientation,
            start,
            end,
            stroke_width,
            source_object_id,
        )
        return cls(
            segment_id=_rule_segment_id(
                source.source_id,
                source.blob_id,
                page_index,
                orientation,
                normalized_start,
                normalized_end,
                width,
                source_object_id,
            ),
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            page_index=page_index,
            orientation=orientation,
            start=normalized_start,
            end=normalized_end,
            stroke_width=width,
            source_object_id=source_object_id,
        )

    @property
    def bounding_box(self) -> BoundingBox:
        return (
            min(self.start[0], self.end[0]),
            min(self.start[1], self.end[1]),
            max(self.start[0], self.end[0]),
            max(self.start[1], self.end[1]),
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_CONTRACT_VERSION:
            raise ValueError("unsupported table rule segment version")
        start, end, width = _validate_rule_parts(
            self.source_id,
            self.source_blob_id,
            self.page_index,
            self.orientation,
            self.start,
            self.end,
            self.stroke_width,
            self.source_object_id,
        )
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        object.__setattr__(self, "stroke_width", width)
        expected = _rule_segment_id(
            self.source_id,
            self.source_blob_id,
            self.page_index,
            self.orientation,
            start,
            end,
            width,
            self.source_object_id,
        )
        if self.segment_id != expected:
            raise ValueError("table rule segment ID is inconsistent")


@dataclass(frozen=True)
class TablePageRuleEvidence:
    evidence_id: str
    source_id: str
    source_blob_id: str
    source_content_hash: str
    page_index: int
    page_width: float
    page_height: float
    rotation_degrees: int
    coordinate_system: str
    segments: tuple[TableRuleSegment, ...]
    ignored_drawing_item_count: int
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    contract_version: str = TABLE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source: SourceDocument,
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
    ) -> TablePageRuleEvidence:
        _validate_page_rules(
            source.source_id,
            source.blob_id,
            source.content_hash,
            page_index,
            page_width,
            page_height,
            rotation_degrees,
            segments,
            ignored_drawing_item_count,
            processor_name,
            processor_version,
            backend_name,
            backend_version,
        )
        evidence_id = _page_rule_evidence_id(
            source.source_id,
            source.blob_id,
            source.content_hash,
            page_index,
            page_width,
            page_height,
            rotation_degrees,
            segments,
            ignored_drawing_item_count,
            processor_name,
            processor_version,
            backend_name,
            backend_version,
        )
        return cls(
            evidence_id=evidence_id,
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            source_content_hash=source.content_hash,
            page_index=page_index,
            page_width=page_width,
            page_height=page_height,
            rotation_degrees=rotation_degrees,
            coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
            segments=segments,
            ignored_drawing_item_count=ignored_drawing_item_count,
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_CONTRACT_VERSION:
            raise ValueError("unsupported table page-rule version")
        if self.coordinate_system != PYMUPDF_COORDINATE_SYSTEM:
            raise ValueError("unsupported table rule coordinate system")
        _validate_page_rules(
            self.source_id,
            self.source_blob_id,
            self.source_content_hash,
            self.page_index,
            self.page_width,
            self.page_height,
            self.rotation_degrees,
            self.segments,
            self.ignored_drawing_item_count,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        expected = _page_rule_evidence_id(
            self.source_id,
            self.source_blob_id,
            self.source_content_hash,
            self.page_index,
            self.page_width,
            self.page_height,
            self.rotation_degrees,
            self.segments,
            self.ignored_drawing_item_count,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        if self.evidence_id != expected:
            raise ValueError("table page-rule evidence ID is inconsistent")


@dataclass(frozen=True)
class TableTextAssociation:
    association_id: str
    role: TableAssociationRole
    page_index: int
    block_id: str
    text: str
    source_spans: tuple[SourceSpan, ...]
    confidence: float
    evidence: Metadata
    contract_version: str = TABLE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        role: TableAssociationRole,
        page_index: int,
        block: ExtractedBlock,
        confidence: float,
        evidence: Metadata,
    ) -> TableTextAssociation:
        normalized = _validate_association_parts(
            role,
            page_index,
            block.block_id,
            block.text,
            block.source_spans,
            confidence,
            evidence,
        )
        return cls(
            association_id=_association_id(
                role,
                page_index,
                block.block_id,
                block.text,
                block.source_spans,
                normalized,
                evidence,
            ),
            role=role,
            page_index=page_index,
            block_id=block.block_id,
            text=block.text or "",
            source_spans=block.source_spans,
            confidence=normalized,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_CONTRACT_VERSION:
            raise ValueError("unsupported table text-association version")
        normalized = _validate_association_parts(
            self.role,
            self.page_index,
            self.block_id,
            self.text,
            self.source_spans,
            self.confidence,
            self.evidence,
        )
        object.__setattr__(self, "confidence", normalized)
        expected = _association_id(
            self.role,
            self.page_index,
            self.block_id,
            self.text,
            self.source_spans,
            normalized,
            self.evidence,
        )
        if self.association_id != expected:
            raise ValueError("table text-association ID is inconsistent")


@dataclass(frozen=True)
class TableDetectionInput:
    input_id: str
    document: ExtractedDocument
    layouts: tuple[PageLayoutResult, ...]
    page_rule_evidence: tuple[TablePageRuleEvidence, ...]
    configuration: TableDetectionConfiguration
    contract_version: str = TABLE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        document: ExtractedDocument,
        layouts: tuple[PageLayoutResult, ...],
        page_rule_evidence: tuple[TablePageRuleEvidence, ...],
        configuration: TableDetectionConfiguration | None = None,
    ) -> TableDetectionInput:
        actual = configuration or TableDetectionConfiguration()
        _validate_input_parts(document, layouts, page_rule_evidence, actual)
        return cls(
            input_id=_input_id(document, layouts, page_rule_evidence, actual),
            document=document,
            layouts=layouts,
            page_rule_evidence=page_rule_evidence,
            configuration=actual,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_CONTRACT_VERSION:
            raise ValueError("unsupported table detection-input version")
        _validate_input_parts(
            self.document,
            self.layouts,
            self.page_rule_evidence,
            self.configuration,
        )
        if self.input_id != _input_id(
            self.document,
            self.layouts,
            self.page_rule_evidence,
            self.configuration,
        ):
            raise ValueError("table detection-input ID is inconsistent")


@dataclass(frozen=True)
class TableRegionEvidence:
    region_evidence_id: str
    detection_input_id: str
    page_index: int
    source_bounding_box: BoundingBox
    block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    row_band_count: int
    column_band_count: int
    rule_segment_ids: tuple[str, ...]
    merged_cell_signal_block_ids: tuple[str, ...]
    rendered_region: RenderedRegion
    confidence: float
    evidence: Metadata
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = TABLE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
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
    ) -> TableRegionEvidence:
        normalized_box, normalized_confidence = _validate_region_parts(
            detection_input_id,
            page_index,
            source_bounding_box,
            block_ids,
            source_spans,
            row_band_count,
            column_band_count,
            rule_segment_ids,
            merged_cell_signal_block_ids,
            rendered_region,
            confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        region_id = _table_region_id(
            detection_input_id,
            page_index,
            normalized_box,
            block_ids,
            source_spans,
            row_band_count,
            column_band_count,
            rule_segment_ids,
            merged_cell_signal_block_ids,
            rendered_region.region_id,
            normalized_confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            region_evidence_id=region_id,
            detection_input_id=detection_input_id,
            page_index=page_index,
            source_bounding_box=normalized_box,
            block_ids=block_ids,
            source_spans=source_spans,
            row_band_count=row_band_count,
            column_band_count=column_band_count,
            rule_segment_ids=rule_segment_ids,
            merged_cell_signal_block_ids=merged_cell_signal_block_ids,
            rendered_region=rendered_region,
            confidence=normalized_confidence,
            evidence=evidence,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_CONTRACT_VERSION:
            raise ValueError("unsupported table region-evidence version")
        box, confidence = _validate_region_parts(
            self.detection_input_id,
            self.page_index,
            self.source_bounding_box,
            self.block_ids,
            self.source_spans,
            self.row_band_count,
            self.column_band_count,
            self.rule_segment_ids,
            self.merged_cell_signal_block_ids,
            self.rendered_region,
            self.confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        object.__setattr__(self, "source_bounding_box", box)
        object.__setattr__(self, "confidence", confidence)
        expected = _table_region_id(
            self.detection_input_id,
            self.page_index,
            box,
            self.block_ids,
            self.source_spans,
            self.row_band_count,
            self.column_band_count,
            self.rule_segment_ids,
            self.merged_cell_signal_block_ids,
            self.rendered_region.region_id,
            confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        if self.region_evidence_id != expected:
            raise ValueError("table region-evidence ID is inconsistent")


@dataclass(frozen=True)
class TableCandidate:
    candidate_id: str
    detection_input_id: str
    boundary_kind: TableBoundaryKind
    evidence_status: TableEvidenceStatus
    source_label: str | None
    regions: tuple[TableRegionEvidence, ...]
    associations: tuple[TableTextAssociation, ...]
    source_spans: tuple[SourceSpan, ...]
    confidence: float
    evidence: Metadata
    warning_ids: tuple[str, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = TABLE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
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
    ) -> TableCandidate:
        normalized = _validate_candidate_parts(
            detection_input_id,
            boundary_kind,
            evidence_status,
            source_label,
            regions,
            associations,
            source_spans,
            confidence,
            evidence,
            warning_ids,
            processor_name,
            processor_version,
            configuration_digest,
        )
        candidate_id = _table_candidate_id(
            detection_input_id,
            boundary_kind,
            evidence_status,
            source_label,
            regions,
            associations,
            source_spans,
            normalized,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            candidate_id=candidate_id,
            detection_input_id=detection_input_id,
            boundary_kind=boundary_kind,
            evidence_status=evidence_status,
            source_label=source_label,
            regions=regions,
            associations=associations,
            source_spans=source_spans,
            confidence=normalized,
            evidence=evidence,
            warning_ids=warning_ids,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_CONTRACT_VERSION:
            raise ValueError("unsupported table candidate version")
        normalized = _validate_candidate_parts(
            self.detection_input_id,
            self.boundary_kind,
            self.evidence_status,
            self.source_label,
            self.regions,
            self.associations,
            self.source_spans,
            self.confidence,
            self.evidence,
            self.warning_ids,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        object.__setattr__(self, "confidence", normalized)
        expected = _table_candidate_id(
            self.detection_input_id,
            self.boundary_kind,
            self.evidence_status,
            self.source_label,
            self.regions,
            self.associations,
            self.source_spans,
            normalized,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        if self.candidate_id != expected:
            raise ValueError("table candidate ID is inconsistent")


@dataclass(frozen=True)
class TableDetectionResult:
    result_id: str
    detection_input: TableDetectionInput
    candidates: tuple[TableCandidate, ...]
    warnings: tuple[IngestionWarning, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = TABLE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        detection_input: TableDetectionInput,
        candidates: tuple[TableCandidate, ...],
        warnings: tuple[IngestionWarning, ...],
        processor_name: str,
        processor_version: str,
    ) -> TableDetectionResult:
        _preflight_result(
            detection_input,
            candidates,
            warnings,
            processor_name,
            processor_version,
        )
        digest = detection_input.configuration.configuration_digest
        _validate_retained_size(
            (
                detection_input,
                candidates,
                warnings,
                processor_name,
                processor_version,
                digest,
            ),
            detection_input.configuration.max_result_bytes,
        )
        return cls(
            result_id=_result_id(
                detection_input.input_id,
                candidates,
                warnings,
                processor_name,
                processor_version,
                digest,
            ),
            detection_input=detection_input,
            candidates=candidates,
            warnings=warnings,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_CONTRACT_VERSION:
            raise ValueError("unsupported table detection-result version")
        _preflight_result(
            self.detection_input,
            self.candidates,
            self.warnings,
            self.processor_name,
            self.processor_version,
        )
        _validate_result(self)
        expected = _result_id(
            self.detection_input.input_id,
            self.candidates,
            self.warnings,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        if self.result_id != expected:
            raise ValueError("table detection-result ID is inconsistent")


class PyMuPdfTableRuleInspector:
    """Inspect bounded vector drawing evidence from exact PDF bytes."""

    name = "pymupdf-table-rule-inspector"
    version = TABLE_RULE_INSPECTOR_VERSION

    def inspect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
        configuration: TableDetectionConfiguration,
    ) -> tuple[TablePageRuleEvidence, ...]:
        from projectkoios.ingestion.tables.inspection import (
            inspect_pdf_table_rules,
        )

        return inspect_pdf_table_rules(self, document, content, configuration)


class DeterministicTableCandidateDetector:
    """Detect bounded table evidence without performing cell extraction."""

    name = "deterministic-table-candidate-detector"
    version = TABLE_DETECTOR_VERSION

    def __init__(
        self,
        configuration: TableDetectionConfiguration | None = None,
        *,
        layout_processor: _PageLayoutProcessor | None = None,
        region_renderer: _PageRegionRenderer | None = None,
        rule_inspector: _TableRuleInspector | None = None,
    ) -> None:
        self.configuration = configuration or TableDetectionConfiguration()
        self.layout_processor = (
            layout_processor or DeterministicLayoutProcessor()
        )
        self.region_renderer = region_renderer or PyMuPdfRegionRenderer(
            max_total_pixels=_MAX_TOTAL_RENDERED_PIXELS,
            max_total_raster_bytes=_MAX_TOTAL_RENDERED_PNG_BYTES,
        )
        self.rule_inspector = rule_inspector or PyMuPdfTableRuleInspector()

    @property
    def configuration_digest(self) -> str:
        return self.configuration.configuration_digest

    def detect(
        self, document: ExtractedDocument, content: BinaryIO
    ) -> TableDetectionResult:
        layouts = self.layout_processor.analyze(document)
        return self.detect_with_layout(document, content, layouts)

    def detect_with_layout(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
        layouts: tuple[PageLayoutResult, ...],
    ) -> TableDetectionResult:
        from projectkoios.ingestion.tables.detection import (
            detect_table_candidates,
        )

        return detect_table_candidates(self, document, content, layouts)


def _validate_input_parts(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    page_rules: tuple[TablePageRuleEvidence, ...],
    configuration: TableDetectionConfiguration,
) -> None:
    from projectkoios.ingestion.tables.validation import (
        _validate_input_parts as validate,
    )

    validate(document, layouts, page_rules, configuration)


def _input_id(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    page_rules: tuple[TablePageRuleEvidence, ...],
    configuration: TableDetectionConfiguration,
) -> str:
    return stable_id(
        "table-detection-input",
        TABLE_CONTRACT_VERSION,
        document.source.source_id,
        document.source.blob_id,
        document.source.content_hash,
        tuple(
            (
                page.page_index,
                tuple(
                    (
                        block.block_id,
                        block.kind,
                        block.text,
                        tuple(
                            span.identity_parts() for span in block.source_spans
                        ),
                    )
                    for block in page.blocks
                ),
            )
            for page in document.pages
        ),
        tuple(layout.result_id for layout in layouts),
        tuple(item.evidence_id for item in page_rules),
        configuration.identity_parts(),
    )


def _validate_result(result: TableDetectionResult) -> None:
    from projectkoios.ingestion.tables.validation import (
        _validate_result as validate,
    )

    validate(result)


def _validate_region_against_input(
    region: TableRegionEvidence, detection_input: TableDetectionInput
) -> None:
    from projectkoios.ingestion.tables.validation import (
        _validate_region_against_input as validate,
    )

    validate(region, detection_input)


def _preflight_result(
    detection_input: TableDetectionInput,
    candidates: tuple[TableCandidate, ...],
    warnings: tuple[IngestionWarning, ...],
    processor_name: str,
    processor_version: str,
) -> None:
    from projectkoios.ingestion.tables.validation import (
        _preflight_result as validate,
    )

    validate(
        detection_input, candidates, warnings, processor_name, processor_version
    )


def _validate_rendered_aggregate(
    regions: tuple[RenderedRegion, ...],
    configuration: TableDetectionConfiguration,
) -> None:
    from projectkoios.ingestion.tables.validation import (
        _validate_rendered_aggregate as validate,
    )

    validate(regions, configuration)


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
    from projectkoios.ingestion.tables.validation import (
        _validate_rule_parts as validate,
    )

    return validate(
        source_id,
        source_blob_id,
        page_index,
        orientation,
        start,
        end,
        stroke_width,
        source_object_id,
    )


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
    from projectkoios.ingestion.tables.validation import (
        _validate_page_rules as validate,
    )

    validate(
        source_id,
        source_blob_id,
        source_content_hash,
        page_index,
        page_width,
        page_height,
        rotation_degrees,
        segments,
        ignored_drawing_item_count,
        processor_name,
        processor_version,
        backend_name,
        backend_version,
    )


def _validate_association_parts(
    role: TableAssociationRole,
    page_index: int,
    block_id: str,
    text: str | None,
    source_spans: tuple[SourceSpan, ...],
    confidence: float,
    evidence: Metadata,
) -> float:
    from projectkoios.ingestion.tables.validation import (
        _validate_association_parts as validate,
    )

    return validate(
        role, page_index, block_id, text, source_spans, confidence, evidence
    )


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
    from projectkoios.ingestion.tables.validation import (
        _validate_region_parts as validate,
    )

    return validate(
        detection_input_id,
        page_index,
        source_bounding_box,
        block_ids,
        source_spans,
        row_band_count,
        column_band_count,
        rule_segment_ids,
        merged_cell_signal_block_ids,
        rendered_region,
        confidence,
        evidence,
        processor_name,
        processor_version,
        configuration_digest,
    )


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
    from projectkoios.ingestion.tables.validation import (
        _validate_candidate_parts as validate,
    )

    return validate(
        detection_input_id,
        boundary_kind,
        evidence_status,
        source_label,
        regions,
        associations,
        source_spans,
        confidence,
        evidence,
        warning_ids,
        processor_name,
        processor_version,
        configuration_digest,
    )


def _rule_segment_id(
    source_id: str,
    source_blob_id: str,
    page_index: int,
    orientation: TableRuleOrientation,
    start: tuple[float, float],
    end: tuple[float, float],
    stroke_width: float,
    source_object_id: str,
) -> str:
    return stable_id(
        "table-rule-segment",
        source_id,
        source_blob_id,
        page_index,
        orientation.value,
        start,
        end,
        stroke_width,
        source_object_id,
    )


def _page_rule_evidence_id(
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
) -> str:
    return stable_id(
        "table-page-rule-evidence",
        source_id,
        source_blob_id,
        source_content_hash,
        page_index,
        page_width,
        page_height,
        rotation_degrees,
        tuple(segment.segment_id for segment in segments),
        ignored_drawing_item_count,
        processor_name,
        processor_version,
        backend_name,
        backend_version,
    )


def _association_id(
    role: TableAssociationRole,
    page_index: int,
    block_id: str,
    text: str | None,
    source_spans: tuple[SourceSpan, ...],
    confidence: float,
    evidence: Metadata,
) -> str:
    return stable_id(
        "table-text-association",
        role.value,
        page_index,
        block_id,
        text,
        tuple(span.identity_parts() for span in source_spans),
        confidence,
        evidence,
    )


def _table_region_id(
    detection_input_id: str,
    page_index: int,
    source_bounding_box: BoundingBox,
    block_ids: tuple[str, ...],
    source_spans: tuple[SourceSpan, ...],
    row_band_count: int,
    column_band_count: int,
    rule_segment_ids: tuple[str, ...],
    merged_cell_signal_block_ids: tuple[str, ...],
    rendered_region_id: str,
    confidence: float,
    evidence: Metadata,
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "table-region-evidence",
        detection_input_id,
        page_index,
        source_bounding_box,
        block_ids,
        tuple(span.identity_parts() for span in source_spans),
        row_band_count,
        column_band_count,
        rule_segment_ids,
        merged_cell_signal_block_ids,
        rendered_region_id,
        confidence,
        evidence,
        processor_name,
        processor_version,
        configuration_digest,
    )


def _table_candidate_id(
    detection_input_id: str,
    boundary_kind: TableBoundaryKind,
    evidence_status: TableEvidenceStatus,
    source_label: str | None,
    regions: tuple[TableRegionEvidence, ...],
    associations: tuple[TableTextAssociation, ...],
    source_spans: tuple[SourceSpan, ...],
    confidence: float,
    evidence: Metadata,
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "table-candidate",
        detection_input_id,
        boundary_kind.value,
        evidence_status.value,
        source_label,
        tuple(region.region_evidence_id for region in regions),
        tuple(association.association_id for association in associations),
        tuple(span.identity_parts() for span in source_spans),
        confidence,
        evidence,
        processor_name,
        processor_version,
        configuration_digest,
    )


def _result_id(
    input_id: str,
    candidates: tuple[TableCandidate, ...],
    warnings: tuple[IngestionWarning, ...],
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "table-detection-result",
        input_id,
        tuple(
            (candidate.candidate_id, candidate.warning_ids)
            for candidate in candidates
        ),
        tuple(
            (
                warning.warning_id,
                warning.code,
                warning.severity.value,
                warning.message,
                warning.object_ids,
                tuple(span.identity_parts() for span in warning.source_spans),
                warning.evidence,
                warning.suggested_recovery,
            )
            for warning in warnings
        ),
        processor_name,
        processor_version,
        configuration_digest,
    )


def _block_box(spans: tuple[SourceSpan, ...]) -> BoundingBox | None:
    boxes = tuple(
        span.bounding_box for span in spans if span.bounding_box is not None
    )
    if not boxes:
        return None
    try:
        return _validated_box(
            (
                min(box[0] for box in boxes),
                min(box[1] for box in boxes),
                max(box[2] for box in boxes),
                max(box[3] for box in boxes),
            )
        )
    except TypeError, ValueError:
        return None


def _padded_box(
    box: BoundingBox,
    page_width: float,
    page_height: float,
    padding: float,
) -> BoundingBox:
    return _validated_box(
        (
            max(0.0, box[0] - padding),
            max(0.0, box[1] - padding),
            min(page_width, box[2] + padding),
            min(page_height, box[3] + padding),
        )
    )


def _expand_box(box: BoundingBox, amount: float) -> BoundingBox:
    return (
        box[0] - amount,
        box[1] - amount,
        box[2] + amount,
        box[3] + amount,
    )


def _boxes_intersect(left: BoundingBox, right: BoundingBox) -> bool:
    return not (
        left[2] < right[0]
        or right[2] < left[0]
        or left[3] < right[1]
        or right[3] < left[1]
    )


def _box_contains(outer: BoundingBox, inner: BoundingBox) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def _union_boxes(boxes: tuple[BoundingBox, ...]) -> BoundingBox:
    if not boxes:
        raise ValueError("cannot union an empty box collection")
    return _validated_box(
        (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
    )


def _validated_box(value: object) -> BoundingBox:
    if not isinstance(value, tuple) or len(value) != 4:
        raise TypeError("bounding box must be an immutable four-value tuple")
    x0, y0, x1, y1 = (
        _finite_float("bounding-box coordinate", item) for item in value
    )
    if x1 <= x0 or y1 <= y0:
        raise ValueError("bounding box must have positive area")
    return (x0, y0, x1, y1)


def _point(name: str, value: object) -> tuple[float, float]:
    if not isinstance(value, tuple) or len(value) != 2:
        raise TypeError(f"{name} must be an immutable two-value tuple")
    return (
        _finite_float(f"{name} x", value[0]),
        _finite_float(f"{name} y", value[1]),
    )


def _point_from_backend(value: object) -> tuple[float, float]:
    point = cast(Any, value)
    try:
        return (float(point.x), float(point.y))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("PyMuPDF returned an invalid drawing point") from error


def _validate_spans(spans: tuple[SourceSpan, ...]) -> None:
    if not isinstance(spans, tuple) or not spans:
        raise ValueError("source spans must be a non-empty immutable tuple")
    if len(spans) > _MAX_SOURCE_SPANS:
        raise TableDetectionLimitError("source spans exceed their hard limit")
    for span in spans:
        if not isinstance(span, SourceSpan):
            raise TypeError("source spans contain an unsupported value")


def _validate_metadata(value: Metadata) -> None:
    if not isinstance(value, tuple):
        raise TypeError("metadata must be an immutable tuple")
    total = 0
    for entry in value:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("metadata must contain immutable key/value pairs")
        key, item = entry
        _bounded_string("metadata key", key, nonempty=True)
        _bounded_string("metadata value", item)
        total += len(key) + len(item)
        if total > _MAX_METADATA_CHARACTERS:
            raise TableDetectionLimitError("metadata exceeds its hard limit")


def _unique_strings(
    name: str, values: tuple[str, ...], *, required: bool = False
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be an immutable tuple")
    if required and not values:
        raise ValueError(f"{name} must be non-empty")
    for value in values:
        _bounded_string(name, value, nonempty=True)
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _bounded_string(
    name: str,
    value: object,
    *,
    nonempty: bool = False,
    limit: int = _MAX_IDENTITY_CHARACTERS,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if nonempty and not value:
        raise ValueError(f"{name} must be non-empty")
    if len(value) > limit:
        raise TableDetectionLimitError(f"{name} exceeds its hard limit")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _positive_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _nonnegative_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _positive_float(name: str, value: object) -> float:
    result = _finite_float(name, value)
    if result <= 0.0:
        raise ValueError(f"{name} must be positive")
    return result


def _nonnegative_float(name: str, value: object) -> float:
    result = _finite_float(name, value)
    if result < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return result


def _unit_float(name: str, value: object) -> float:
    result = _finite_float(name, value)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be within [0, 1]")
    return result


def _validate_sha256(name: str, value: str) -> None:
    _bounded_string(name, value, nonempty=True)
    if len(value) != 64:
        raise ValueError(f"{name} must be a SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError(f"{name} must be a SHA-256 hex digest") from error


def _validate_retained_size(value: object, limit: int) -> None:
    from projectkoios.ingestion.tables.validation import (
        _validate_retained_size as validate,
    )

    validate(value, limit)


def _axis_segments(
    item: object,
) -> tuple[tuple[tuple[float, float], tuple[float, float], str], ...]:
    """Return bounded axis-aligned segments for a backend drawing item."""
    from projectkoios.ingestion.tables.inspection import (
        _axis_segments as inspect_axis_segments,
    )

    return inspect_axis_segments(item)


_COMPATIBILITY_TYPES = (
    DeterministicTableCandidateDetector,
    PyMuPdfTableRuleInspector,
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
)
for _compatibility_type in _COMPATIBILITY_TYPES:
    _compatibility_type.__module__ = "projectkoios.ingestion.tables"
del _compatibility_type


__all__ = [
    "TABLE_CONTRACT_VERSION",
    "TABLE_DETECTOR_VERSION",
    "TABLE_RULE_INSPECTOR_VERSION",
    "DeterministicTableCandidateDetector",
    "PyMuPdfTableRuleInspector",
    "TableAssociationRole",
    "TableBoundaryKind",
    "TableCandidate",
    "TableDetectionConfiguration",
    "TableDetectionInput",
    "TableDetectionLimitError",
    "TableDetectionResult",
    "TableEvidenceStatus",
    "TablePageRuleEvidence",
    "TableRegionEvidence",
    "TableRuleOrientation",
    "TableRuleSegment",
    "TableTextAssociation",
]

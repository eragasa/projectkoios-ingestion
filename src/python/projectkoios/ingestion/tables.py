from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, fields, is_dataclass, replace
from enum import Enum, StrEnum
from io import BytesIO
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
    WarningSeverity,
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
_MAX_DRAWINGS_PER_PAGE = 100_000
_MAX_DRAWING_ITEMS_PER_PAGE = 200_000
_MAX_RULE_SEGMENTS_PER_PAGE = 100_000
_MAX_TOTAL_RULE_SEGMENTS = 200_000
_MAX_CANDIDATES = 256
_MAX_REGIONS_PER_CANDIDATE = 64
_MAX_BLOCKS_PER_REGION = 2_048
_MAX_ASSOCIATIONS_PER_CANDIDATE = 256
_MAX_WARNINGS = 4_096
_MAX_RESULT_BYTES = 128_000_000
_MAX_TOTAL_RENDERED_PNG_BYTES = 100_000_000
_MAX_TOTAL_RENDERED_PIXELS = 25_000_000
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
    """Lazily inspect bounded axis-aligned PDF vector line evidence."""

    name = "pymupdf-table-rule-inspector"
    version = TABLE_RULE_INSPECTOR_VERSION

    def inspect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
        configuration: TableDetectionConfiguration,
    ) -> tuple[TablePageRuleEvidence, ...]:
        payload = _read_exact_payload(document.source, content, configuration)
        try:
            import pymupdf
        except ImportError as error:
            from projectkoios.ingestion.pdf.extractor import (
                PdfDependencyUnavailableError,
            )

            raise PdfDependencyUnavailableError(
                "PDF table-rule inspection requires the optional "
                "PyMuPDF dependency"
            ) from error
        backend_name = "PyMuPDF"
        backend_version = str(getattr(pymupdf, "VersionBind", "unknown"))
        pdf = pymupdf.open(stream=payload, filetype="pdf")
        try:
            if len(pdf) != len(document.pages):
                raise ValueError(
                    "PDF page count does not match extracted document"
                )
            results: list[TablePageRuleEvidence] = []
            total_segments = 0
            for page_offset, extracted_page in enumerate(document.pages):
                pdf_page = pdf[page_offset]
                if (
                    float(pdf_page.cropbox.width) != extracted_page.width
                    or float(pdf_page.cropbox.height) != extracted_page.height
                    or int(pdf_page.rotation) != extracted_page.rotation_degrees
                ):
                    raise ValueError(
                        "PDF page geometry does not match extracted document"
                    )
                drawings = pdf_page.get_drawings()
                if len(drawings) > configuration.max_drawings_per_page:
                    raise TableDetectionLimitError(
                        "drawings exceed max_drawings_per_page"
                    )
                segments: list[TableRuleSegment] = []
                item_count = 0
                ignored_item_count = 0
                for drawing_index, drawing in enumerate(drawings):
                    items = drawing.get("items", ())
                    item_count += len(items)
                    if item_count > configuration.max_drawing_items_per_page:
                        raise TableDetectionLimitError(
                            "drawing items exceed max_drawing_items_per_page"
                        )
                    width = _nonnegative_float(
                        "drawing stroke width", drawing.get("width", 0.0)
                    )
                    has_stroke = drawing.get("color") is not None
                    for item_index, item in enumerate(items):
                        axis_segments = (
                            _axis_segments(item) if has_stroke else ()
                        )
                        if not axis_segments:
                            ignored_item_count += 1
                        for start, end, suffix in axis_segments:
                            orientation = (
                                TableRuleOrientation.VERTICAL
                                if start[0] == end[0]
                                else TableRuleOrientation.HORIZONTAL
                            )
                            segment = TableRuleSegment.create(
                                source=document.source,
                                page_index=extracted_page.page_index,
                                orientation=orientation,
                                start=start,
                                end=end,
                                stroke_width=width,
                                source_object_id=(
                                    f"page:{extracted_page.page_index}:"
                                    f"drawing:{drawing_index}:item:{item_index}:"
                                    f"segment:{suffix}"
                                ),
                            )
                            segments.append(segment)
                            if len(segments) > (
                                configuration.max_rule_segments_per_page
                            ):
                                raise TableDetectionLimitError(
                                    "rule segments exceed their per-page limit"
                                )
                            total_segments += 1
                            if total_segments > (
                                configuration.max_total_rule_segments
                            ):
                                raise TableDetectionLimitError(
                                    "rule segments exceed their aggregate limit"
                                )
                results.append(
                    TablePageRuleEvidence.create(
                        source=document.source,
                        page_index=extracted_page.page_index,
                        page_width=extracted_page.width,
                        page_height=extracted_page.height,
                        rotation_degrees=extracted_page.rotation_degrees,
                        segments=tuple(segments),
                        ignored_drawing_item_count=ignored_item_count,
                        processor_name=self.name,
                        processor_version=self.version,
                        backend_name=backend_name,
                        backend_version=backend_version,
                    )
                )
            return tuple(results)
        finally:
            pdf.close()


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


class DeterministicTableCandidateDetector:
    """Detect and render conservative table-shaped source evidence."""

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
        self.region_renderer = region_renderer or PyMuPdfRegionRenderer()
        self.rule_inspector = rule_inspector or PyMuPdfTableRuleInspector()

    @property
    def configuration_digest(self) -> str:
        return self.configuration.configuration_digest

    def detect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
    ) -> TableDetectionResult:
        layouts = self.layout_processor.analyze(document)
        return self.detect_with_layout(document, content, layouts)

    def detect_with_layout(
        self,
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
            > configuration.max_drawing_items_per_page
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
    if ignored_drawing_item_count > _MAX_DRAWING_ITEMS_PER_PAGE:
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


def _axis_segments(
    item: object,
) -> tuple[tuple[tuple[float, float], tuple[float, float], str], ...]:
    if not isinstance(item, tuple) or not item:
        return ()
    kind = item[0]
    if kind == "l" and len(item) >= 3:
        start = _point_from_backend(item[1])
        end = _point_from_backend(item[2])
        if start[0] == end[0] or start[1] == end[1]:
            return ((start, end, "line"),)
        return ()
    if kind == "re" and len(item) >= 2:
        rectangle = item[1]
        try:
            x0 = float(rectangle.x0)
            y0 = float(rectangle.y0)
            x1 = float(rectangle.x1)
            y1 = float(rectangle.y1)
        except (AttributeError, TypeError, ValueError):
            return ()
        return (
            ((x0, y0), (x1, y0), "rect-top"),
            ((x1, y0), (x1, y1), "rect-right"),
            ((x1, y1), (x0, y1), "rect-bottom"),
            ((x0, y1), (x0, y0), "rect-left"),
        )
    return ()


def _read_exact_payload(
    source: SourceDocument,
    content: BinaryIO,
    configuration: TableDetectionConfiguration,
) -> bytes:
    if source.byte_length > configuration.max_source_bytes:
        raise TableDetectionLimitError("source exceeds max_source_bytes")
    payload = content.read(configuration.max_source_bytes + 1)
    if not isinstance(payload, bytes):
        raise TypeError("PDF content stream must return bytes")
    if len(payload) > configuration.max_source_bytes:
        raise TableDetectionLimitError("source exceeds max_source_bytes")
    digest = hashlib.sha256(payload).hexdigest()
    if len(payload) != source.byte_length or digest != source.content_hash:
        raise ValueError("source bytes do not agree with SourceDocument")
    return payload


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
    except (TypeError, ValueError):
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

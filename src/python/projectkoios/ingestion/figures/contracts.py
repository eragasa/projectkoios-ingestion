"""Contracts and deterministic facades for figure detection."""

from __future__ import annotations

import hashlib
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
    ExtractedPage,
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

FIGURE_CONTRACT_VERSION = "1.0"
FIGURE_DETECTOR_VERSION = "1"
FIGURE_INSPECTOR_VERSION = "1"
_MAX_SOURCE_BYTES = 1_000_000_000
_MAX_PAGES = 512
_MAX_INPUT_BLOCKS = 16_384
_MAX_TEXT_BLOCKS = 8_192
_MAX_TEXT_CHARACTERS = 5_000_000
_MAX_SOURCE_SPANS = 250_000
_MAX_EMBEDDED_ASSETS = 8_192
_MAX_EMBEDDED_ASSET_BYTES = 100_000_000
_MAX_TOTAL_EMBEDDED_BYTES = 100_000_000
_MAX_BACKEND_DRAWINGS_PER_PAGE = 2_000_000
_MAX_BACKEND_DRAWING_ITEMS_PER_PAGE = 10_000_000
_MAX_DRAWINGS_PER_PAGE = 100_000
_MAX_DRAWING_ITEMS_PER_PAGE = 500_000
_MAX_TOTAL_DRAWINGS = 200_000
_MAX_DRAWING_GROUP_COMPARISONS = 10_000_000
_MAX_CANDIDATES = 256
_MAX_COMPONENTS = 4_096
_MAX_ASSOCIATIONS = 16_384
_MAX_ASSOCIATION_COMPARISONS = 10_000_000
_MAX_WARNINGS = 4_096
_MAX_RESULT_BYTES = 128_000_000
_MAX_TOTAL_RENDERED_PNG_BYTES = 100_000_000
_MAX_TOTAL_RENDERED_PIXELS = 100_000_000
_MAX_IDENTITY_CHARACTERS = 4_096
_MAX_TEXT_FIELD_CHARACTERS = 65_536
_MAX_METADATA_CHARACTERS = 100_000
_FIGURE_CAPTION = re.compile(
    r"^\s*(?P<prefix>Figure\b|Fig\.)\s*"
    r"(?P<label>(?:[A-Za-z]?\d+(?:[.\-]\d+)*|[IVXLCDM]+|[A-Za-z]))?"
    r"(?P<subfigure>\s*\([A-Za-z0-9]+\))?\s*[:.\-]?\s*",
    re.IGNORECASE,
)
_SUBFIGURE_LABEL = re.compile(r"^\s*\([A-Za-z0-9]+\)\s*(?:$|\S)")
_LEGEND = re.compile(r"^\s*(?:Legend|Key)\s*[:.]", re.IGNORECASE)


class FigureDetectionLimitError(ValueError):
    """Raised before figure detection exceeds a configured hard bound."""


class FigureEvidenceStatus(StrEnum):
    """Proposal status with no accepted or validated state."""

    PROPOSED = "proposed"
    AMBIGUOUS = "ambiguous"


class FigureArtifactKind(StrEnum):
    EMBEDDED_IMAGE = "embedded_image"
    RENDERED_DRAWING = "rendered_drawing"


class FigureAssociationRole(StrEnum):
    CAPTION = "caption"
    SUBFIGURE_LABEL = "subfigure_label"
    LEGEND = "legend"


class _PageLayoutProcessor(Protocol):
    def analyze(
        self, document: ExtractedDocument
    ) -> tuple[PageLayoutResult, ...]: ...


class _PageRegionRenderer(Protocol):
    name: str
    version: str

    def render(
        self,
        source: SourceDocument,
        content: BinaryIO,
        selections: tuple[PageRegionSelection, ...],
    ) -> tuple[RenderedRegion, ...]: ...


class _FigureInspector(Protocol):
    name: str
    version: str

    def inspect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
        configuration: FigureDetectionConfiguration,
    ) -> tuple[FigurePageEvidence, ...]: ...


@dataclass(frozen=True)
class FigureDetectionConfiguration:
    max_source_bytes: int = _MAX_SOURCE_BYTES
    max_pages: int = _MAX_PAGES
    max_input_blocks: int = _MAX_INPUT_BLOCKS
    max_text_blocks: int = _MAX_TEXT_BLOCKS
    max_text_characters: int = _MAX_TEXT_CHARACTERS
    max_source_spans: int = _MAX_SOURCE_SPANS
    max_embedded_assets: int = _MAX_EMBEDDED_ASSETS
    max_embedded_asset_bytes: int = _MAX_EMBEDDED_ASSET_BYTES
    max_total_embedded_bytes: int = _MAX_TOTAL_EMBEDDED_BYTES
    max_backend_drawings_per_page: int = _MAX_BACKEND_DRAWINGS_PER_PAGE
    max_backend_drawing_items_per_page: int = (
        _MAX_BACKEND_DRAWING_ITEMS_PER_PAGE
    )
    max_drawings_per_page: int = _MAX_DRAWINGS_PER_PAGE
    max_drawing_items_per_page: int = _MAX_DRAWING_ITEMS_PER_PAGE
    max_total_drawings: int = _MAX_TOTAL_DRAWINGS
    max_drawing_group_comparisons: int = _MAX_DRAWING_GROUP_COMPARISONS
    max_candidates: int = _MAX_CANDIDATES
    max_components: int = _MAX_COMPONENTS
    max_associations: int = _MAX_ASSOCIATIONS
    max_association_comparisons: int = 1_000_000
    max_warnings: int = _MAX_WARNINGS
    max_result_bytes: int = _MAX_RESULT_BYTES
    max_total_rendered_png_bytes: int = _MAX_TOTAL_RENDERED_PNG_BYTES
    max_total_rendered_pixels: int = _MAX_TOTAL_RENDERED_PIXELS
    association_distance_points: float = 96.0
    drawing_group_gap_points: float = 24.0
    render_padding_points: float = 6.0
    minimum_drawing_dimension_points: float = 4.0
    minimum_drawing_area_points: float = 64.0
    maximum_legend_characters: int = 512
    proposed_confidence_threshold: float = 0.70

    def __post_init__(self) -> None:
        for name, hard_maximum in (
            ("max_source_bytes", _MAX_SOURCE_BYTES),
            ("max_pages", _MAX_PAGES),
            ("max_input_blocks", _MAX_INPUT_BLOCKS),
            ("max_text_blocks", _MAX_TEXT_BLOCKS),
            ("max_text_characters", _MAX_TEXT_CHARACTERS),
            ("max_source_spans", _MAX_SOURCE_SPANS),
            ("max_embedded_assets", _MAX_EMBEDDED_ASSETS),
            ("max_embedded_asset_bytes", _MAX_EMBEDDED_ASSET_BYTES),
            ("max_total_embedded_bytes", _MAX_TOTAL_EMBEDDED_BYTES),
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
            ("max_total_drawings", _MAX_TOTAL_DRAWINGS),
            (
                "max_drawing_group_comparisons",
                _MAX_DRAWING_GROUP_COMPARISONS,
            ),
            ("max_candidates", _MAX_CANDIDATES),
            ("max_components", _MAX_COMPONENTS),
            ("max_associations", _MAX_ASSOCIATIONS),
            (
                "max_association_comparisons",
                _MAX_ASSOCIATION_COMPARISONS,
            ),
            ("max_warnings", _MAX_WARNINGS),
            ("max_result_bytes", _MAX_RESULT_BYTES),
            (
                "max_total_rendered_png_bytes",
                _MAX_TOTAL_RENDERED_PNG_BYTES,
            ),
            ("max_total_rendered_pixels", _MAX_TOTAL_RENDERED_PIXELS),
            ("maximum_legend_characters", _MAX_TEXT_FIELD_CHARACTERS),
        ):
            value = getattr(self, name)
            _positive_integer(name, value)
            if value > hard_maximum:
                raise FigureDetectionLimitError(
                    f"{name} exceeds its implementation maximum "
                    f"({hard_maximum})"
                )
        for name, upper in (
            ("association_distance_points", 720.0),
            ("drawing_group_gap_points", 144.0),
            ("render_padding_points", 72.0),
            ("minimum_drawing_dimension_points", 144.0),
            ("minimum_drawing_area_points", 20_736.0),
        ):
            value = _finite_float(name, getattr(self, name))
            if not 0.0 <= value <= upper:
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
        return stable_id(
            "figure-detection-configuration", self.identity_parts()
        )

    def identity_parts(self) -> tuple[object, ...]:
        return tuple(
            (name, getattr(self, name)) for name in self.__dataclass_fields__
        )


@dataclass(frozen=True)
class EmbeddedFigureArtifact:
    artifact_id: str
    source_id: str
    source_blob_id: str
    source_content_hash: str
    page_index: int
    source_block_id: str
    source_spans: tuple[SourceSpan, ...]
    source_bounding_box: BoundingBox
    asset_id: str
    media_type: str
    width_pixels: int
    height_pixels: int
    byte_length: int
    content_sha256: str
    content: bytes
    mask_asset_id: str | None
    mask_media_type: str | None
    mask_byte_length: int | None
    mask_content_sha256: str | None
    mask_content: bytes | None
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    contract_version: str = FIGURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source: SourceDocument,
        page_index: int,
        block: ExtractedBlock,
        content: bytes,
        mask_content: bytes | None,
        width_pixels: int,
        height_pixels: int,
        processor_name: str,
        processor_version: str,
        backend_name: str,
        backend_version: str,
    ) -> EmbeddedFigureArtifact:
        if block.kind != "image" or block.asset_id is None:
            raise ValueError("embedded artifact requires an image block")
        _positive_integer("artifact pixel width", width_pixels)
        _positive_integer("artifact pixel height", height_pixels)
        box = _block_box(block)
        content_hash = hashlib.sha256(content).hexdigest()
        mask_hash = (
            hashlib.sha256(mask_content).hexdigest()
            if mask_content is not None
            else None
        )
        artifact_id = stable_id(
            "embedded-figure-artifact",
            source.source_id,
            source.blob_id,
            page_index,
            block.block_id,
            tuple(span.identity_parts() for span in block.source_spans),
            box,
            block.asset_id,
            block.asset_media_type,
            width_pixels,
            height_pixels,
            content_hash,
            len(content),
            block.asset_mask_id,
            block.asset_mask_media_type,
            mask_hash,
            len(mask_content) if mask_content is not None else None,
            processor_name,
            processor_version,
            backend_name,
            backend_version,
        )
        return cls(
            artifact_id=artifact_id,
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            source_content_hash=source.content_hash,
            page_index=page_index,
            source_block_id=block.block_id,
            source_spans=block.source_spans,
            source_bounding_box=box,
            asset_id=block.asset_id,
            media_type=block.asset_media_type or "application/octet-stream",
            width_pixels=width_pixels,
            height_pixels=height_pixels,
            byte_length=len(content),
            content_sha256=content_hash,
            content=content,
            mask_asset_id=block.asset_mask_id,
            mask_media_type=block.asset_mask_media_type,
            mask_byte_length=(
                len(mask_content) if mask_content is not None else None
            ),
            mask_content_sha256=mask_hash,
            mask_content=mask_content,
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_CONTRACT_VERSION:
            raise ValueError("unsupported embedded figure-artifact version")
        _identity_fields(
            self.source_id,
            self.source_blob_id,
            self.source_block_id,
            self.asset_id,
            self.media_type,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        _sha256("source content hash", self.source_content_hash)
        _nonnegative_integer("artifact page index", self.page_index)
        _positive_integer("artifact pixel width", self.width_pixels)
        _positive_integer("artifact pixel height", self.height_pixels)
        _validate_spans(self.source_spans)
        box = _validated_box(self.source_bounding_box)
        object.__setattr__(self, "source_bounding_box", box)
        if not isinstance(self.content, bytes):
            raise TypeError("embedded artifact content must be immutable bytes")
        if not self.content:
            raise ValueError("embedded artifact content must be non-empty")
        if self.byte_length != len(self.content):
            raise ValueError("embedded artifact byte length is inconsistent")
        digest = hashlib.sha256(self.content).hexdigest()
        if (
            self.content_sha256 != digest
            or self.asset_id != f"asset:sha256:{digest}"
        ):
            raise ValueError(
                "embedded artifact content identity is inconsistent"
            )
        mask_values = (
            self.mask_asset_id,
            self.mask_media_type,
            self.mask_byte_length,
            self.mask_content_sha256,
            self.mask_content,
        )
        if any(value is not None for value in mask_values):
            if any(value is None for value in mask_values):
                raise ValueError(
                    "embedded artifact mask evidence must be complete"
                )
            if not isinstance(self.mask_content, bytes):
                raise TypeError("embedded mask content must be immutable bytes")
            if not self.mask_content:
                raise ValueError("embedded mask content must be non-empty")
            mask_digest = hashlib.sha256(self.mask_content).hexdigest()
            if (
                self.mask_byte_length != len(self.mask_content)
                or self.mask_content_sha256 != mask_digest
                or self.mask_asset_id != f"asset:sha256:{mask_digest}"
            ):
                raise ValueError(
                    "embedded artifact mask identity is inconsistent"
                )
        expected = stable_id(
            "embedded-figure-artifact",
            self.source_id,
            self.source_blob_id,
            self.page_index,
            self.source_block_id,
            tuple(span.identity_parts() for span in self.source_spans),
            box,
            self.asset_id,
            self.media_type,
            self.width_pixels,
            self.height_pixels,
            self.content_sha256,
            self.byte_length,
            self.mask_asset_id,
            self.mask_media_type,
            self.mask_content_sha256,
            self.mask_byte_length,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        if self.artifact_id != expected:
            raise ValueError("embedded figure-artifact ID is inconsistent")


@dataclass(frozen=True)
class FigureDrawingEvidence:
    drawing_id: str
    source_id: str
    source_blob_id: str
    page_index: int
    source_span: SourceSpan
    source_bounding_box: BoundingBox
    source_object_id: str
    item_count: int
    has_stroke: bool
    has_fill: bool
    contract_version: str = FIGURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source: SourceDocument,
        page_index: int,
        printed_page_label: str | None,
        source_bounding_box: BoundingBox,
        source_object_id: str,
        item_count: int,
        has_stroke: bool,
        has_fill: bool,
    ) -> FigureDrawingEvidence:
        box = _validated_extent_box(source_bounding_box)
        span = SourceSpan(
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            source_object_id=source_object_id,
            bounding_box=box,
        )
        drawing_id = stable_id(
            "figure-drawing-evidence",
            source.source_id,
            source.blob_id,
            page_index,
            span.identity_parts(),
            item_count,
            has_stroke,
            has_fill,
        )
        return cls(
            drawing_id=drawing_id,
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            page_index=page_index,
            source_span=span,
            source_bounding_box=box,
            source_object_id=source_object_id,
            item_count=item_count,
            has_stroke=has_stroke,
            has_fill=has_fill,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_CONTRACT_VERSION:
            raise ValueError("unsupported figure drawing-evidence version")
        _identity_fields(
            self.source_id, self.source_blob_id, self.source_object_id
        )
        _nonnegative_integer("drawing page index", self.page_index)
        _positive_integer("drawing item count", self.item_count)
        if not isinstance(self.has_stroke, bool) or not isinstance(
            self.has_fill, bool
        ):
            raise TypeError("drawing stroke/fill indicators must be booleans")
        box = _validated_extent_box(self.source_bounding_box)
        object.__setattr__(self, "source_bounding_box", box)
        if (
            self.source_span.source_id != self.source_id
            or self.source_span.source_blob_id != self.source_blob_id
            or self.source_span.page_index != self.page_index
            or self.source_span.source_object_id != self.source_object_id
            or self.source_span.bounding_box != box
        ):
            raise ValueError("drawing source span is inconsistent")
        expected = stable_id(
            "figure-drawing-evidence",
            self.source_id,
            self.source_blob_id,
            self.page_index,
            self.source_span.identity_parts(),
            self.item_count,
            self.has_stroke,
            self.has_fill,
        )
        if self.drawing_id != expected:
            raise ValueError("figure drawing-evidence ID is inconsistent")


@dataclass(frozen=True)
class FigurePageEvidence:
    evidence_id: str
    source_id: str
    source_blob_id: str
    source_content_hash: str
    page_index: int
    page_width: float
    page_height: float
    rotation_degrees: int
    coordinate_system: str
    embedded_artifacts: tuple[EmbeddedFigureArtifact, ...]
    drawings: tuple[FigureDrawingEvidence, ...]
    ignored_drawing_count: int
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    contract_version: str = FIGURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source: SourceDocument,
        page: ExtractedPage,
        embedded_artifacts: tuple[EmbeddedFigureArtifact, ...],
        drawings: tuple[FigureDrawingEvidence, ...],
        ignored_drawing_count: int,
        processor_name: str,
        processor_version: str,
        backend_name: str,
        backend_version: str,
    ) -> FigurePageEvidence:
        evidence_id = _page_evidence_id(
            source,
            page,
            embedded_artifacts,
            drawings,
            ignored_drawing_count,
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
            page_index=page.page_index,
            page_width=page.width,
            page_height=page.height,
            rotation_degrees=page.rotation_degrees,
            coordinate_system=page.coordinate_system,
            embedded_artifacts=embedded_artifacts,
            drawings=drawings,
            ignored_drawing_count=ignored_drawing_count,
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_CONTRACT_VERSION:
            raise ValueError("unsupported figure page-evidence version")
        _identity_fields(
            self.source_id,
            self.source_blob_id,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        _sha256("page evidence source hash", self.source_content_hash)
        _nonnegative_integer("page evidence index", self.page_index)
        width = _positive_float("page evidence width", self.page_width)
        height = _positive_float("page evidence height", self.page_height)
        object.__setattr__(self, "page_width", width)
        object.__setattr__(self, "page_height", height)
        if self.coordinate_system != PYMUPDF_COORDINATE_SYSTEM:
            raise ValueError("figure evidence coordinate system is unsupported")
        if self.rotation_degrees not in (0, 90, 180, 270):
            raise ValueError("figure evidence rotation is unsupported")
        _require_tuple("embedded artifacts", self.embedded_artifacts)
        _require_tuple("drawing evidence", self.drawings)
        if any(
            not isinstance(item, EmbeddedFigureArtifact)
            for item in self.embedded_artifacts
        ) or any(
            not isinstance(item, FigureDrawingEvidence)
            for item in self.drawings
        ):
            raise TypeError(
                "figure page evidence contains an unsupported value"
            )
        _nonnegative_integer(
            "ignored drawing count", self.ignored_drawing_count
        )
        expected = stable_id(
            "figure-page-evidence",
            self.source_id,
            self.source_blob_id,
            self.source_content_hash,
            self.page_index,
            width,
            height,
            self.rotation_degrees,
            self.coordinate_system,
            tuple(item.artifact_id for item in self.embedded_artifacts),
            tuple(item.drawing_id for item in self.drawings),
            self.ignored_drawing_count,
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        if self.evidence_id != expected:
            raise ValueError("figure page-evidence ID is inconsistent")


@dataclass(frozen=True)
class FigureDetectionInput:
    input_id: str
    document: ExtractedDocument
    layouts: tuple[PageLayoutResult, ...]
    page_evidence: tuple[FigurePageEvidence, ...]
    configuration: FigureDetectionConfiguration
    contract_version: str = FIGURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        document: ExtractedDocument,
        layouts: tuple[PageLayoutResult, ...],
        page_evidence: tuple[FigurePageEvidence, ...],
        configuration: FigureDetectionConfiguration | None = None,
    ) -> FigureDetectionInput:
        actual = configuration or FigureDetectionConfiguration()
        _validate_input_parts(document, layouts, page_evidence, actual)
        return cls(
            input_id=_input_id(document, layouts, page_evidence, actual),
            document=document,
            layouts=layouts,
            page_evidence=page_evidence,
            configuration=actual,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_CONTRACT_VERSION:
            raise ValueError("unsupported figure detection-input version")
        _validate_input_parts(
            self.document, self.layouts, self.page_evidence, self.configuration
        )
        if self.input_id != _input_id(
            self.document,
            self.layouts,
            self.page_evidence,
            self.configuration,
        ):
            raise ValueError("figure detection-input ID is inconsistent")


@dataclass(frozen=True)
class FigureTextAssociation:
    association_id: str
    role: FigureAssociationRole
    page_index: int
    block_id: str
    component_id: str | None
    text: str
    source_spans: tuple[SourceSpan, ...]
    confidence: float
    evidence: Metadata
    contract_version: str = FIGURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        role: FigureAssociationRole,
        page_index: int,
        block: ExtractedBlock,
        component_id: str | None,
        confidence: float,
        evidence: Metadata,
    ) -> FigureTextAssociation:
        if block.kind != "text" or block.text is None:
            raise ValueError("figure text association requires a text block")
        normalized = _unit_float("association confidence", confidence)
        association_id = stable_id(
            "figure-text-association",
            role.value,
            page_index,
            block.block_id,
            component_id,
            block.text,
            tuple(span.identity_parts() for span in block.source_spans),
            normalized,
            evidence,
        )
        return cls(
            association_id=association_id,
            role=role,
            page_index=page_index,
            block_id=block.block_id,
            component_id=component_id,
            text=block.text,
            source_spans=block.source_spans,
            confidence=normalized,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_CONTRACT_VERSION:
            raise ValueError("unsupported figure association version")
        if not isinstance(self.role, FigureAssociationRole):
            raise TypeError("figure association role is unsupported")
        _nonnegative_integer("association page index", self.page_index)
        _identity_fields(self.block_id)
        if self.component_id is not None:
            _identity_fields(self.component_id)
        _bounded_text("association text", self.text)
        _validate_spans(self.source_spans)
        confidence = _unit_float("association confidence", self.confidence)
        object.__setattr__(self, "confidence", confidence)
        _validate_metadata(self.evidence)
        expected = stable_id(
            "figure-text-association",
            self.role.value,
            self.page_index,
            self.block_id,
            self.component_id,
            self.text,
            tuple(span.identity_parts() for span in self.source_spans),
            confidence,
            self.evidence,
        )
        if self.association_id != expected:
            raise ValueError("figure association ID is inconsistent")


@dataclass(frozen=True)
class FigureComponent:
    component_id: str
    detection_input_id: str
    page_index: int
    component_index: int
    artifact_kind: FigureArtifactKind
    source_bounding_box: BoundingBox
    source_block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    embedded_artifact_id: str | None
    drawing_evidence_ids: tuple[str, ...]
    rendered_region: RenderedRegion | None
    evidence_status: FigureEvidenceStatus
    confidence: float
    evidence: Metadata
    warning_ids: tuple[str, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = FIGURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        detection_input_id: str,
        page_index: int,
        component_index: int,
        artifact_kind: FigureArtifactKind,
        source_bounding_box: BoundingBox,
        source_block_ids: tuple[str, ...],
        source_spans: tuple[SourceSpan, ...],
        embedded_artifact_id: str | None,
        drawing_evidence_ids: tuple[str, ...],
        rendered_region: RenderedRegion | None,
        evidence_status: FigureEvidenceStatus,
        confidence: float,
        evidence: Metadata,
        warning_ids: tuple[str, ...],
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> FigureComponent:
        box = _validated_box(source_bounding_box)
        normalized = _unit_float("component confidence", confidence)
        component_id = _component_id(
            detection_input_id,
            page_index,
            component_index,
            artifact_kind,
            box,
            source_block_ids,
            source_spans,
            embedded_artifact_id,
            drawing_evidence_ids,
            rendered_region,
            evidence_status,
            normalized,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            component_id=component_id,
            detection_input_id=detection_input_id,
            page_index=page_index,
            component_index=component_index,
            artifact_kind=artifact_kind,
            source_bounding_box=box,
            source_block_ids=source_block_ids,
            source_spans=source_spans,
            embedded_artifact_id=embedded_artifact_id,
            drawing_evidence_ids=drawing_evidence_ids,
            rendered_region=rendered_region,
            evidence_status=evidence_status,
            confidence=normalized,
            evidence=evidence,
            warning_ids=warning_ids,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_CONTRACT_VERSION:
            raise ValueError("unsupported figure component version")
        _identity_fields(
            self.detection_input_id,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        _nonnegative_integer("component page index", self.page_index)
        _nonnegative_integer("component index", self.component_index)
        if not isinstance(self.artifact_kind, FigureArtifactKind):
            raise TypeError("figure artifact kind is unsupported")
        box = _validated_box(self.source_bounding_box)
        object.__setattr__(self, "source_bounding_box", box)
        _unique_strings("component source block IDs", self.source_block_ids)
        _validate_spans(self.source_spans)
        _unique_strings("drawing evidence IDs", self.drawing_evidence_ids)
        _unique_strings("component warning IDs", self.warning_ids)
        if self.artifact_kind is FigureArtifactKind.EMBEDDED_IMAGE:
            if (
                self.embedded_artifact_id is None
                or self.rendered_region is not None
                or self.drawing_evidence_ids
                or not self.source_block_ids
            ):
                raise ValueError(
                    "embedded figure component evidence is inconsistent"
                )
        else:
            if (
                self.embedded_artifact_id is not None
                or self.rendered_region is None
                or not self.drawing_evidence_ids
                or self.source_block_ids
            ):
                raise ValueError(
                    "rendered drawing component evidence is inconsistent"
                )
        if not isinstance(self.evidence_status, FigureEvidenceStatus):
            raise TypeError("component evidence status is unsupported")
        confidence = _unit_float("component confidence", self.confidence)
        object.__setattr__(self, "confidence", confidence)
        _validate_metadata(self.evidence)
        expected = _component_id(
            self.detection_input_id,
            self.page_index,
            self.component_index,
            self.artifact_kind,
            box,
            self.source_block_ids,
            self.source_spans,
            self.embedded_artifact_id,
            self.drawing_evidence_ids,
            self.rendered_region,
            self.evidence_status,
            confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        if self.component_id != expected:
            raise ValueError("figure component ID is inconsistent")


@dataclass(frozen=True)
class FigureCandidate:
    candidate_id: str
    detection_input_id: str
    page_index: int
    source_label: str | None
    source_bounding_box: BoundingBox
    components: tuple[FigureComponent, ...]
    associations: tuple[FigureTextAssociation, ...]
    source_spans: tuple[SourceSpan, ...]
    evidence_status: FigureEvidenceStatus
    confidence: float
    evidence: Metadata
    warning_ids: tuple[str, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = FIGURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        detection_input_id: str,
        page_index: int,
        source_label: str | None,
        source_bounding_box: BoundingBox,
        components: tuple[FigureComponent, ...],
        associations: tuple[FigureTextAssociation, ...],
        source_spans: tuple[SourceSpan, ...],
        evidence_status: FigureEvidenceStatus,
        confidence: float,
        evidence: Metadata,
        warning_ids: tuple[str, ...],
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> FigureCandidate:
        box = _validated_box(source_bounding_box)
        normalized = _unit_float("figure confidence", confidence)
        candidate_id = _candidate_id(
            detection_input_id,
            page_index,
            source_label,
            box,
            components,
            associations,
            source_spans,
            evidence_status,
            normalized,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            candidate_id=candidate_id,
            detection_input_id=detection_input_id,
            page_index=page_index,
            source_label=source_label,
            source_bounding_box=box,
            components=components,
            associations=associations,
            source_spans=source_spans,
            evidence_status=evidence_status,
            confidence=normalized,
            evidence=evidence,
            warning_ids=warning_ids,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_CONTRACT_VERSION:
            raise ValueError("unsupported figure candidate version")
        _identity_fields(
            self.detection_input_id,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        _nonnegative_integer("candidate page index", self.page_index)
        if self.source_label is not None:
            _bounded_string(
                "figure source label", self.source_label, nonempty=True
            )
        box = _validated_box(self.source_bounding_box)
        object.__setattr__(self, "source_bounding_box", box)
        _require_tuple("figure components", self.components)
        _require_tuple("figure associations", self.associations)
        if not self.components:
            raise ValueError("figure candidate requires a component")
        if any(
            not isinstance(item, FigureComponent) for item in self.components
        ):
            raise TypeError("figure components contain an unsupported value")
        if any(
            not isinstance(item, FigureTextAssociation)
            for item in self.associations
        ):
            raise TypeError("figure associations contain an unsupported value")
        _validate_spans(self.source_spans)
        if not isinstance(self.evidence_status, FigureEvidenceStatus):
            raise TypeError("figure evidence status is unsupported")
        confidence = _unit_float("figure confidence", self.confidence)
        object.__setattr__(self, "confidence", confidence)
        _validate_metadata(self.evidence)
        _unique_strings("candidate warning IDs", self.warning_ids)
        expected = _candidate_id(
            self.detection_input_id,
            self.page_index,
            self.source_label,
            box,
            self.components,
            self.associations,
            self.source_spans,
            self.evidence_status,
            confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        if self.candidate_id != expected:
            raise ValueError("figure candidate ID is inconsistent")


@dataclass(frozen=True)
class FigureDetectionResult:
    result_id: str
    detection_input: FigureDetectionInput
    candidates: tuple[FigureCandidate, ...]
    warnings: tuple[IngestionWarning, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = FIGURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        detection_input: FigureDetectionInput,
        candidates: tuple[FigureCandidate, ...],
        warnings: tuple[IngestionWarning, ...],
        processor_name: str,
        processor_version: str,
    ) -> FigureDetectionResult:
        digest = detection_input.configuration.configuration_digest
        result = cls(
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
        _validate_result(result)
        return result

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_CONTRACT_VERSION:
            raise ValueError("unsupported figure detection-result version")
        _validate_result(self)
        if self.result_id != _result_id(
            self.detection_input.input_id,
            self.candidates,
            self.warnings,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        ):
            raise ValueError("figure detection-result ID is inconsistent")


class PyMuPdfFigureInspector:
    """Lazily retain exact embedded bytes and bounded drawing locators."""

    name = "pymupdf-figure-inspector"
    version = FIGURE_INSPECTOR_VERSION

    def inspect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
        configuration: FigureDetectionConfiguration,
    ) -> tuple[FigurePageEvidence, ...]:
        from projectkoios.ingestion.figures.inspection import (
            inspect_pdf_figures,
        )

        return inspect_pdf_figures(self, document, content, configuration)


class DeterministicFigureCandidateDetector:
    """Detect source-backed figures without semantic interpretation."""

    name = "deterministic-figure-candidate-detector"
    version = FIGURE_DETECTOR_VERSION

    def __init__(
        self,
        configuration: FigureDetectionConfiguration | None = None,
        *,
        layout_processor: _PageLayoutProcessor | None = None,
        region_renderer: _PageRegionRenderer | None = None,
        figure_inspector: _FigureInspector | None = None,
    ) -> None:
        self.configuration = configuration or FigureDetectionConfiguration()
        self.layout_processor = (
            layout_processor or DeterministicLayoutProcessor()
        )
        self.region_renderer = region_renderer or PyMuPdfRegionRenderer(
            max_total_pixels=_MAX_TOTAL_RENDERED_PIXELS,
            max_total_raster_bytes=_MAX_TOTAL_RENDERED_PNG_BYTES,
        )
        self.figure_inspector = figure_inspector or PyMuPdfFigureInspector()

    @property
    def configuration_digest(self) -> str:
        return self.configuration.configuration_digest

    def detect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
    ) -> FigureDetectionResult:
        layouts = self.layout_processor.analyze(document)
        return self.detect_with_layout(document, content, layouts)

    def detect_with_layout(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
        layouts: tuple[PageLayoutResult, ...],
    ) -> FigureDetectionResult:
        from projectkoios.ingestion.figures.detection import (
            detect_figure_candidates,
        )

        return detect_figure_candidates(self, document, content, layouts)


def _validate_input_parts(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    page_evidence: tuple[FigurePageEvidence, ...],
    configuration: FigureDetectionConfiguration,
) -> None:
    from projectkoios.ingestion.figures.validation import validate_input_parts

    validate_input_parts(document, layouts, page_evidence, configuration)


def _validate_result(result: FigureDetectionResult) -> None:
    from projectkoios.ingestion.figures.validation import validate_result

    validate_result(result)


def _validate_component_render(
    component: FigureComponent,
    document: ExtractedDocument,
) -> None:
    from projectkoios.ingestion.figures.validation import (
        validate_component_render,
    )

    validate_component_render(component, document)


def _validate_rendered_aggregate(
    regions: tuple[RenderedRegion, ...],
    configuration: FigureDetectionConfiguration,
) -> None:
    from projectkoios.ingestion.figures.validation import (
        validate_rendered_aggregate,
    )

    validate_rendered_aggregate(regions, configuration)


def _input_id(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    page_evidence: tuple[FigurePageEvidence, ...],
    configuration: FigureDetectionConfiguration,
) -> str:
    return stable_id(
        "figure-detection-input",
        FIGURE_CONTRACT_VERSION,
        document.source.source_id,
        document.source.blob_id,
        document.source.content_hash,
        tuple(
            (
                page.page_index,
                page.width,
                page.height,
                page.rotation_degrees,
                page.coordinate_system,
                tuple(
                    (
                        block.block_id,
                        block.kind,
                        block.text,
                        block.asset_id,
                        block.asset_media_type,
                        block.asset_mask_id,
                        block.asset_mask_media_type,
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
        tuple(evidence.evidence_id for evidence in page_evidence),
        configuration.identity_parts(),
    )


def _component_id(
    detection_input_id: str,
    page_index: int,
    component_index: int,
    artifact_kind: FigureArtifactKind,
    source_bounding_box: BoundingBox,
    source_block_ids: tuple[str, ...],
    source_spans: tuple[SourceSpan, ...],
    embedded_artifact_id: str | None,
    drawing_evidence_ids: tuple[str, ...],
    rendered_region: RenderedRegion | None,
    evidence_status: FigureEvidenceStatus,
    confidence: float,
    evidence: Metadata,
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "figure-component",
        detection_input_id,
        page_index,
        component_index,
        artifact_kind.value,
        source_bounding_box,
        source_block_ids,
        tuple(span.identity_parts() for span in source_spans),
        embedded_artifact_id,
        drawing_evidence_ids,
        rendered_region.region_id if rendered_region is not None else None,
        evidence_status.value,
        confidence,
        evidence,
        processor_name,
        processor_version,
        configuration_digest,
    )


def _candidate_id(
    detection_input_id: str,
    page_index: int,
    source_label: str | None,
    source_bounding_box: BoundingBox,
    components: tuple[FigureComponent, ...],
    associations: tuple[FigureTextAssociation, ...],
    source_spans: tuple[SourceSpan, ...],
    evidence_status: FigureEvidenceStatus,
    confidence: float,
    evidence: Metadata,
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "figure-candidate",
        detection_input_id,
        page_index,
        source_label,
        source_bounding_box,
        tuple(component.component_id for component in components),
        tuple(association.association_id for association in associations),
        tuple(span.identity_parts() for span in source_spans),
        evidence_status.value,
        confidence,
        evidence,
        processor_name,
        processor_version,
        configuration_digest,
    )


def _result_id(
    input_id: str,
    candidates: tuple[FigureCandidate, ...],
    warnings: tuple[IngestionWarning, ...],
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "figure-detection-result",
        input_id,
        tuple(
            (
                candidate.candidate_id,
                candidate.warning_ids,
                tuple(
                    (component.component_id, component.warning_ids)
                    for component in candidate.components
                ),
            )
            for candidate in candidates
        ),
        tuple(
            (
                warning.warning_id,
                warning.code,
                warning.object_ids,
                tuple(span.identity_parts() for span in warning.source_spans),
                warning.evidence,
            )
            for warning in warnings
        ),
        processor_name,
        processor_version,
        configuration_digest,
    )


def _page_evidence_id(
    source: SourceDocument,
    page: ExtractedPage,
    artifacts: tuple[EmbeddedFigureArtifact, ...],
    drawings: tuple[FigureDrawingEvidence, ...],
    ignored: int,
    processor_name: str,
    processor_version: str,
    backend_name: str,
    backend_version: str,
) -> str:
    return stable_id(
        "figure-page-evidence",
        source.source_id,
        source.blob_id,
        source.content_hash,
        page.page_index,
        page.width,
        page.height,
        page.rotation_degrees,
        page.coordinate_system,
        tuple(item.artifact_id for item in artifacts),
        tuple(item.drawing_id for item in drawings),
        ignored,
        processor_name,
        processor_version,
        backend_name,
        backend_version,
    )


def _source_label(text: str) -> str | None:
    match = _FIGURE_CAPTION.match(text)
    if match is None:
        return None
    prefix = match.group("prefix")
    label = (match.group("label") or "").strip()
    subfigure = (match.group("subfigure") or "").strip()
    suffix = f"{label}{subfigure}"
    return f"{prefix} {suffix}" if suffix else prefix


def _block_box(block: ExtractedBlock) -> BoundingBox:
    box = _optional_block_box(block)
    if box is None:
        raise ValueError("figure source block lacks positive-area geometry")
    return box


def _optional_block_box(block: ExtractedBlock) -> BoundingBox | None:
    boxes = tuple(
        span.bounding_box
        for span in block.source_spans
        if span.bounding_box is not None and _box_has_area(span.bounding_box)
    )
    if not boxes:
        return None
    return _union_boxes(boxes)


def _union_boxes(boxes: tuple[BoundingBox, ...]) -> BoundingBox:
    box = _union_boxes_allowing_extents(boxes)
    return _validated_box(box)


def _union_boxes_allowing_extents(
    boxes: tuple[BoundingBox, ...],
) -> BoundingBox:
    if not boxes:
        raise ValueError("cannot union an empty set of boxes")
    return _validated_extent_box(
        (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
    )


def _padded_box(
    box: BoundingBox,
    page: ExtractedPage,
    padding: float,
) -> BoundingBox:
    return _validated_box(
        (
            max(0.0, box[0] - padding),
            max(0.0, box[1] - padding),
            min(page.width, box[2] + padding),
            min(page.height, box[3] + padding),
        )
    )


def _boxes_within(left: BoundingBox, right: BoundingBox, gap: float) -> bool:
    return not (
        left[2] + gap < right[0]
        or right[2] + gap < left[0]
        or left[3] + gap < right[1]
        or right[3] + gap < left[1]
    )


def _near_box(left: BoundingBox, right: BoundingBox, distance: float) -> bool:
    return _boxes_within(left, right, distance)


def _axis_gap(a0: float, a1: float, b0: float, b1: float) -> float:
    if a1 < b0:
        return b0 - a1
    if b1 < a0:
        return a0 - b1
    return 0.0


def _box_area(box: BoundingBox) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])


def _box_has_area(value: object) -> bool:
    if not _box_is_ordered(value):
        return False
    box = tuple(float(item) for item in cast(Iterable[Any], value))
    return box[2] > box[0] and box[3] > box[1]


def _box_is_ordered(value: object) -> bool:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return False
    try:
        box = tuple(float(item) for item in value)
    except TypeError, ValueError:
        return False
    return (
        len(box) == 4
        and all(math.isfinite(item) for item in box)
        and box[2] >= box[0]
        and box[3] >= box[1]
    )


def _box_within_page(box: BoundingBox, page: ExtractedPage) -> bool:
    return (
        box[0] >= 0.0
        and box[1] >= 0.0
        and box[2] <= page.width
        and box[3] <= page.height
    )


def _decimal(value: float) -> str:
    return format(value, ".6f").rstrip("0").rstrip(".") or "0"


def _identity_fields(*values: str) -> None:
    for value in values:
        _bounded_string("identity field", value, nonempty=True)


def _unique_strings(
    name: str, values: tuple[str, ...], *, required: bool = False
) -> None:
    _require_tuple(name, values)
    if required and not values:
        raise ValueError(f"{name} must be non-empty")
    for value in values:
        _bounded_string(name, value, nonempty=True)
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _validate_spans(spans: tuple[SourceSpan, ...]) -> None:
    _require_tuple("source spans", spans)
    if not spans:
        raise ValueError("source spans must be non-empty")
    if len(spans) > _MAX_SOURCE_SPANS:
        raise FigureDetectionLimitError("source spans exceed their hard limit")
    if any(not isinstance(span, SourceSpan) for span in spans):
        raise TypeError("source spans contain an unsupported value")


def _validate_metadata(value: Metadata) -> None:
    _require_tuple("metadata", value)
    total = 0
    for entry in value:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("metadata must contain immutable pairs")
        key, item = entry
        _bounded_string("metadata key", key, nonempty=True)
        _bounded_string("metadata value", item)
        total += len(key) + len(item)
    if total > _MAX_METADATA_CHARACTERS:
        raise FigureDetectionLimitError("metadata exceeds its hard limit")


def _require_tuple(name: str, value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be an immutable tuple")


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
        raise FigureDetectionLimitError(f"{name} exceeds its hard limit")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _bounded_text(name: str, value: object) -> None:
    _bounded_string(name, value, limit=_MAX_TEXT_FIELD_CHARACTERS)


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
    return 0.0 if result == 0.0 else result


def _positive_float(name: str, value: object) -> float:
    result = _finite_float(name, value)
    if result <= 0.0:
        raise ValueError(f"{name} must be positive")
    return result


def _unit_float(name: str, value: object) -> float:
    result = _finite_float(name, value)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be within [0, 1]")
    return result


def _validated_box(value: object) -> BoundingBox:
    x0, y0, x1, y1 = _validated_extent_box(value)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("bounding box must have positive area")
    return (x0, y0, x1, y1)


def _validated_extent_box(value: object) -> BoundingBox:
    if not isinstance(value, tuple) or len(value) != 4:
        raise TypeError("bounding box must be an immutable four-value tuple")
    x0, y0, x1, y1 = (
        _finite_float("bounding-box coordinate", item) for item in value
    )
    if x1 < x0 or y1 < y0:
        raise ValueError("bounding box coordinates must be ordered")
    return (x0, y0, x1, y1)


def _sha256(name: str, value: str) -> None:
    if len(value) != 64:
        raise ValueError(f"{name} must be a SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError(f"{name} must be a SHA-256 digest") from error


def _validate_retained_size(value: object, limit: int) -> None:
    from projectkoios.ingestion.figures.validation import (
        validate_retained_size,
    )

    validate_retained_size(value, limit)


_COMPATIBILITY_TYPES = (
    DeterministicFigureCandidateDetector,
    EmbeddedFigureArtifact,
    FigureArtifactKind,
    FigureAssociationRole,
    FigureCandidate,
    FigureComponent,
    FigureDetectionConfiguration,
    FigureDetectionInput,
    FigureDetectionLimitError,
    FigureDetectionResult,
    FigureDrawingEvidence,
    FigureEvidenceStatus,
    FigurePageEvidence,
    FigureTextAssociation,
    PyMuPdfFigureInspector,
)
for _compatibility_type in _COMPATIBILITY_TYPES:
    _compatibility_type.__module__ = "projectkoios.ingestion.figures"
del _compatibility_type


__all__ = [
    "FIGURE_CONTRACT_VERSION",
    "FIGURE_DETECTOR_VERSION",
    "FIGURE_INSPECTOR_VERSION",
    "DeterministicFigureCandidateDetector",
    "EmbeddedFigureArtifact",
    "FigureArtifactKind",
    "FigureAssociationRole",
    "FigureCandidate",
    "FigureComponent",
    "FigureDetectionConfiguration",
    "FigureDetectionInput",
    "FigureDetectionLimitError",
    "FigureDetectionResult",
    "FigureDrawingEvidence",
    "FigureEvidenceStatus",
    "FigurePageEvidence",
    "FigureTextAssociation",
    "PyMuPdfFigureInspector",
]

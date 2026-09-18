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
    LayoutBlockReference,
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
    WarningSeverity,
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


@dataclass(frozen=True)
class _Visual:
    key: str
    page_index: int
    kind: FigureArtifactKind
    box: BoundingBox
    artifact: EmbeddedFigureArtifact | None
    drawings: tuple[FigureDrawingEvidence, ...]
    caption_block: ExtractedBlock | None
    caption_distance: float | None
    selection: PageRegionSelection | None


@dataclass(frozen=True)
class _CandidatePlan:
    page_index: int
    visuals: tuple[_Visual, ...]
    caption_block: ExtractedBlock | None


@dataclass(frozen=True)
class _WarningSpec:
    code: str
    message: str
    source_spans: tuple[SourceSpan, ...]
    evidence: Metadata = ()


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
        payload = _read_exact_payload(document.source, content, configuration)
        try:
            import pymupdf
        except ImportError as error:
            from projectkoios.ingestion.pdf.extractor import (
                PdfDependencyUnavailableError,
            )

            raise PdfDependencyUnavailableError(
                "PDF figure inspection requires the optional PyMuPDF dependency"
            ) from error
        backend_name = "PyMuPDF"
        backend_version = str(getattr(pymupdf, "VersionBind", "")).strip()
        if not backend_version:
            raise RuntimeError("PyMuPDF does not expose its backend version")
        pdf = pymupdf.open(stream=payload, filetype="pdf")
        try:
            if len(pdf) != len(document.pages):
                raise ValueError(
                    "PDF page count does not match extracted document"
                )
            results: list[FigurePageEvidence] = []
            total_assets = 0
            total_asset_bytes = 0
            total_drawings = 0
            for offset, extracted_page in enumerate(document.pages):
                page = pdf[offset]
                _verify_page_geometry(page, extracted_page)
                raw = page.get_text("dict", sort=False)
                raw_blocks = raw.get("blocks", ())
                if len(raw_blocks) > configuration.max_input_blocks:
                    raise FigureDetectionLimitError(
                        "raw PDF blocks exceed max_input_blocks"
                    )
                extracted_by_object = {
                    span.source_object_id: block
                    for block in extracted_page.blocks
                    for span in block.source_spans
                    if span.source_object_id is not None
                }
                artifacts: list[EmbeddedFigureArtifact] = []
                for ordinal, raw_block in enumerate(raw_blocks):
                    if raw_block.get("type") != 1:
                        continue
                    object_id = (
                        f"page:{extracted_page.page_index}:block:{ordinal}"
                    )
                    block = extracted_by_object.get(object_id)
                    if block is None:
                        raise ValueError(
                            "PDF image block is absent from extraction"
                        )
                    image = bytes(raw_block.get("image", b""))
                    mask_value = raw_block.get("mask")
                    mask = bytes(mask_value) if mask_value is not None else None
                    raw_box = tuple(
                        float(value) for value in raw_block.get("bbox", ())
                    )
                    if (
                        len(raw_box) != 4
                        or not _box_has_area(raw_box)
                        or _validated_box(raw_box) != _block_box(block)
                    ):
                        raise ValueError(
                            "PDF image geometry differs from raw extraction"
                        )
                    if block.asset_media_type != _raw_image_media_type(
                        raw_block
                    ):
                        raise ValueError(
                            "PDF image media type differs from raw extraction"
                        )
                    expected_mask_media = (
                        _detect_media_type(mask) if mask is not None else None
                    )
                    if block.asset_mask_media_type != expected_mask_media:
                        raise ValueError(
                            "PDF image mask type differs from raw extraction"
                        )
                    width_pixels = raw_block.get("width", 0)
                    height_pixels = raw_block.get("height", 0)
                    _positive_integer("artifact pixel width", width_pixels)
                    _positive_integer("artifact pixel height", height_pixels)
                    if len(image) > configuration.max_embedded_asset_bytes or (
                        mask is not None
                        and len(mask) > configuration.max_embedded_asset_bytes
                    ):
                        raise FigureDetectionLimitError(
                            "embedded asset exceeds max_embedded_asset_bytes"
                        )
                    total_asset_bytes += len(image) + (len(mask) if mask else 0)
                    if (
                        total_asset_bytes
                        > configuration.max_total_embedded_bytes
                    ):
                        raise FigureDetectionLimitError(
                            "embedded assets exceed max_total_embedded_bytes"
                        )
                    artifacts.append(
                        EmbeddedFigureArtifact.create(
                            source=document.source,
                            page_index=extracted_page.page_index,
                            block=block,
                            content=image,
                            mask_content=mask,
                            width_pixels=cast(int, width_pixels),
                            height_pixels=cast(int, height_pixels),
                            processor_name=self.name,
                            processor_version=self.version,
                            backend_name=backend_name,
                            backend_version=backend_version,
                        )
                    )
                    total_assets += 1
                    if total_assets > configuration.max_embedded_assets:
                        raise FigureDetectionLimitError(
                            "embedded assets exceed max_embedded_assets"
                        )
                expected_image_ids = tuple(
                    block.block_id
                    for block in extracted_page.blocks
                    if block.kind == "image"
                )
                if (
                    tuple(item.source_block_id for item in artifacts)
                    != expected_image_ids
                ):
                    raise ValueError(
                        "embedded artifact extraction is incomplete"
                    )
                raw_drawings = page.get_drawings()
                if (
                    len(raw_drawings)
                    > configuration.max_backend_drawings_per_page
                ):
                    raise FigureDetectionLimitError(
                        "backend drawings exceed their per-page limit"
                    )
                backend_item_count = sum(
                    len(drawing.get("items", ())) for drawing in raw_drawings
                )
                if (
                    backend_item_count
                    > configuration.max_backend_drawing_items_per_page
                ):
                    raise FigureDetectionLimitError(
                        "backend drawing items exceed their per-page limit"
                    )
                retain_stroked_only = (
                    len(raw_drawings) > configuration.max_drawings_per_page
                )
                drawings: list[FigureDrawingEvidence] = []
                ignored = 0
                item_count = 0
                for drawing_index, drawing in enumerate(raw_drawings):
                    items = drawing.get("items", ())
                    has_stroke = drawing.get("color") is not None
                    if retain_stroked_only and not has_stroke:
                        ignored += 1
                        continue
                    item_count += len(items)
                    if item_count > configuration.max_drawing_items_per_page:
                        raise FigureDetectionLimitError(
                            "retained drawing items exceed their per-page limit"
                        )
                    box_value = tuple(
                        float(value) for value in drawing.get("rect", ())
                    )
                    if len(box_value) != 4 or not _box_is_ordered(box_value):
                        ignored += 1
                        continue
                    box = _validated_extent_box(box_value)
                    if not _box_within_page(box, extracted_page):
                        ignored += 1
                        continue
                    if not items:
                        ignored += 1
                        continue
                    drawings.append(
                        FigureDrawingEvidence.create(
                            source=document.source,
                            page_index=extracted_page.page_index,
                            printed_page_label=extracted_page.printed_page_label,
                            source_bounding_box=box,
                            source_object_id=(
                                f"page:{extracted_page.page_index}:"
                                f"drawing:{drawing_index}"
                            ),
                            item_count=len(items),
                            has_stroke=has_stroke,
                            has_fill=drawing.get("fill") is not None,
                        )
                    )
                    if len(drawings) > configuration.max_drawings_per_page:
                        raise FigureDetectionLimitError(
                            "retained drawings exceed their per-page limit"
                        )
                    total_drawings += 1
                    if total_drawings > configuration.max_total_drawings:
                        raise FigureDetectionLimitError(
                            "drawings exceed max_total_drawings"
                        )
                results.append(
                    FigurePageEvidence.create(
                        source=document.source,
                        page=extracted_page,
                        embedded_artifacts=tuple(artifacts),
                        drawings=tuple(drawings),
                        ignored_drawing_count=ignored,
                        processor_name=self.name,
                        processor_version=self.version,
                        backend_name=backend_name,
                        backend_version=backend_version,
                    )
                )
            return tuple(results)
        finally:
            pdf.close()


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
        payload = _read_exact_payload(
            document.source, content, self.configuration
        )
        page_evidence = self.figure_inspector.inspect(
            document, BytesIO(payload), self.configuration
        )
        detection_input = FigureDetectionInput.create(
            document=document,
            layouts=layouts,
            page_evidence=page_evidence,
            configuration=self.configuration,
        )
        caption_comparisons = sum(
            (len(evidence.embedded_artifacts) + len(evidence.drawings))
            * sum(
                block.kind == "text"
                and block.text is not None
                and _FIGURE_CAPTION.match(block.text) is not None
                for block in page.blocks
            )
            for page, evidence in zip(
                document.pages, page_evidence, strict=True
            )
        )
        if caption_comparisons > self.configuration.max_association_comparisons:
            raise FigureDetectionLimitError(
                "association comparisons exceed max_association_comparisons"
            )
        plans, ignored_specs = _plan_candidates(detection_input)
        if len(plans) > self.configuration.max_candidates:
            raise FigureDetectionLimitError("figures exceed max_candidates")
        component_count = sum(len(plan.visuals) for plan in plans)
        if component_count > self.configuration.max_components:
            raise FigureDetectionLimitError("components exceed max_components")
        text_counts = {
            page.page_index: sum(block.kind == "text" for block in page.blocks)
            for page in document.pages
        }
        association_comparisons = caption_comparisons + sum(
            len(plan.visuals) * text_counts[plan.page_index] for plan in plans
        )
        if (
            association_comparisons
            > self.configuration.max_association_comparisons
        ):
            raise FigureDetectionLimitError(
                "association comparisons exceed max_association_comparisons"
            )
        selections = tuple(
            visual.selection
            for plan in plans
            for visual in plan.visuals
            if visual.selection is not None
        )
        rendered_by_selection: dict[PageRegionSelection, RenderedRegion] = {}
        if selections:
            rendered = self.region_renderer.render(
                document.source, BytesIO(payload), selections
            )
            if len(rendered) != len(selections):
                raise ValueError("renderer returned an unexpected result count")
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
        candidates: list[FigureCandidate] = []
        candidate_specs: list[list[_WarningSpec]] = []
        for plan in plans:
            components = tuple(
                _component_from_visual(
                    detection_input,
                    visual,
                    component_index,
                    rendered_by_selection,
                    self.name,
                    self.version,
                )
                for component_index, visual in enumerate(plan.visuals)
            )
            associations = _associations_for_plan(
                detection_input, plan, components
            )
            source_spans = tuple(
                span
                for component in components
                for span in component.source_spans
            )
            caption = next(
                (
                    association
                    for association in associations
                    if association.role is FigureAssociationRole.CAPTION
                ),
                None,
            )
            source_label = (
                _source_label(caption.text) if caption is not None else None
            )
            plan_specs: list[_WarningSpec] = []
            confidence = min(component.confidence for component in components)
            if caption is None:
                confidence = max(0.0, confidence - 0.25)
                plan_specs.append(
                    _WarningSpec(
                        code="figure.caption_missing",
                        message=(
                            "Embedded figure evidence has no associated caption"
                        ),
                        source_spans=source_spans,
                    )
                )
            else:
                confidence = min(1.0, confidence + 0.08)
            if confidence < self.configuration.proposed_confidence_threshold:
                plan_specs.append(
                    _WarningSpec(
                        code="figure.low_confidence",
                        message=(
                            "Figure confidence is below the configured "
                            "proposal threshold"
                        ),
                        source_spans=source_spans,
                    )
                )
            status = (
                FigureEvidenceStatus.AMBIGUOUS
                if plan_specs
                else FigureEvidenceStatus.PROPOSED
            )
            box = _union_boxes(
                tuple(component.source_bounding_box for component in components)
            )
            candidate = FigureCandidate.create(
                detection_input_id=detection_input.input_id,
                page_index=plan.page_index,
                source_label=source_label,
                source_bounding_box=box,
                components=components,
                associations=associations,
                source_spans=source_spans,
                evidence_status=status,
                confidence=confidence,
                evidence=(
                    ("component_count", str(len(components))),
                    ("caption_present", str(caption is not None).lower()),
                ),
                warning_ids=(),
                processor_name=self.name,
                processor_version=self.version,
                configuration_digest=self.configuration_digest,
            )
            candidates.append(candidate)
            candidate_specs.append(plan_specs)
        if (
            len(ignored_specs) + sum(len(specs) for specs in candidate_specs)
            > self.configuration.max_warnings
        ):
            raise FigureDetectionLimitError("warnings exceed max_warnings")
        warnings, final_candidates = _materialize_warnings(
            tuple(candidates), tuple(candidate_specs), ignored_specs
        )
        if len(warnings) > self.configuration.max_warnings:
            raise FigureDetectionLimitError("warnings exceed max_warnings")
        return FigureDetectionResult.create(
            detection_input=detection_input,
            candidates=final_candidates,
            warnings=warnings,
            processor_name=self.name,
            processor_version=self.version,
        )


def _plan_candidates(
    detection_input: FigureDetectionInput,
) -> tuple[tuple[_CandidatePlan, ...], tuple[_WarningSpec, ...]]:
    configuration = detection_input.configuration
    document = detection_input.document
    evidence_by_page = {
        evidence.page_index: evidence
        for evidence in detection_input.page_evidence
    }
    plans: list[_CandidatePlan] = []
    ignored: list[_WarningSpec] = []
    for page in document.pages:
        evidence = evidence_by_page[page.page_index]
        text_blocks = tuple(
            block for block in page.blocks if block.kind == "text"
        )
        captions = tuple(
            block
            for block in text_blocks
            if block.text is not None and _FIGURE_CAPTION.match(block.text)
        )
        visuals: list[_Visual] = []
        for artifact in evidence.embedded_artifacts:
            caption, distance = _nearest_caption(
                artifact.source_bounding_box, captions, configuration
            )
            visuals.append(
                _Visual(
                    key=artifact.artifact_id,
                    page_index=page.page_index,
                    kind=FigureArtifactKind.EMBEDDED_IMAGE,
                    box=artifact.source_bounding_box,
                    artifact=artifact,
                    drawings=(),
                    caption_block=caption,
                    caption_distance=distance,
                    selection=None,
                )
            )
        for group in _drawing_groups(evidence.drawings, configuration):
            box = _union_boxes(
                tuple(item.source_bounding_box for item in group)
            )
            caption, distance = _nearest_caption(box, captions, configuration)
            if caption is None:
                if len(ignored) >= configuration.max_warnings:
                    raise FigureDetectionLimitError(
                        "warnings exceed max_warnings"
                    )
                ignored.append(
                    _WarningSpec(
                        code="figure.unassociated_drawing_ignored",
                        message=(
                            "Drawing evidence without a nearby explicit figure "
                            "caption was not promoted"
                        ),
                        source_spans=tuple(item.source_span for item in group),
                        evidence=(("page_index", str(page.page_index)),),
                    )
                )
                continue
            selection_box = _padded_box(
                box,
                page,
                configuration.render_padding_points,
            )
            selection = PageRegionSelection.for_bounding_box(
                document.source, page.page_index, selection_box
            )
            key = stable_id(
                "drawing-visual",
                tuple(item.drawing_id for item in group),
                selection.identity_parts(),
            )
            visuals.append(
                _Visual(
                    key=key,
                    page_index=page.page_index,
                    kind=FigureArtifactKind.RENDERED_DRAWING,
                    box=box,
                    artifact=None,
                    drawings=group,
                    caption_block=caption,
                    caption_distance=distance,
                    selection=selection,
                )
            )
        grouped: dict[str, list[_Visual]] = {}
        captions_by_key: dict[str, ExtractedBlock | None] = {}
        for visual in visuals:
            key = (
                visual.caption_block.block_id
                if visual.caption_block is not None
                else visual.key
            )
            grouped.setdefault(key, []).append(visual)
            captions_by_key[key] = visual.caption_block
        for key, items in grouped.items():
            plans.append(
                _CandidatePlan(
                    page_index=page.page_index,
                    visuals=tuple(
                        sorted(
                            items,
                            key=lambda item: (
                                item.box[1],
                                item.box[0],
                                item.key,
                            ),
                        )
                    ),
                    caption_block=captions_by_key[key],
                )
            )
        matched_caption_ids = {
            visual.caption_block.block_id
            for visual in visuals
            if visual.caption_block is not None
        }
        for caption in captions:
            if caption.block_id not in matched_caption_ids:
                if len(ignored) >= configuration.max_warnings:
                    raise FigureDetectionLimitError(
                        "warnings exceed max_warnings"
                    )
                ignored.append(
                    _WarningSpec(
                        code="figure.caption_without_visual",
                        message=(
                            "An explicit figure caption has no nearby embedded "
                            "or drawing evidence"
                        ),
                        source_spans=caption.source_spans,
                    )
                )
    plans.sort(
        key=lambda plan: (
            plan.page_index,
            min(visual.box[1] for visual in plan.visuals),
            min(visual.box[0] for visual in plan.visuals),
        )
    )
    return tuple(plans), tuple(ignored)


def _component_from_visual(
    detection_input: FigureDetectionInput,
    visual: _Visual,
    component_index: int,
    rendered_by_selection: dict[PageRegionSelection, RenderedRegion],
    processor_name: str,
    processor_version: str,
) -> FigureComponent:
    source_block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    if visual.artifact is not None:
        source_block_ids = (visual.artifact.source_block_id,)
        source_spans = visual.artifact.source_spans
        artifact_id = visual.artifact.artifact_id
        drawing_ids: tuple[str, ...] = ()
        rendered = None
        confidence = 0.92
        evidence: Metadata = (("method", "embedded_image_bytes"),)
    else:
        if visual.selection is None:
            raise ValueError("drawing visual lacks a render selection")
        source_block_ids = ()
        source_spans = tuple(item.source_span for item in visual.drawings)
        artifact_id = None
        drawing_ids = tuple(item.drawing_id for item in visual.drawings)
        rendered = rendered_by_selection[visual.selection]
        confidence = 0.78
        evidence = (("method", "rendered_pdf_drawing_commands"),)
    return FigureComponent.create(
        detection_input_id=detection_input.input_id,
        page_index=visual.page_index,
        component_index=component_index,
        artifact_kind=visual.kind,
        source_bounding_box=visual.box,
        source_block_ids=source_block_ids,
        source_spans=source_spans,
        embedded_artifact_id=artifact_id,
        drawing_evidence_ids=drawing_ids,
        rendered_region=rendered,
        evidence_status=FigureEvidenceStatus.PROPOSED,
        confidence=confidence,
        evidence=evidence,
        warning_ids=(),
        processor_name=processor_name,
        processor_version=processor_version,
        configuration_digest=detection_input.configuration.configuration_digest,
    )


def _associations_for_plan(
    detection_input: FigureDetectionInput,
    plan: _CandidatePlan,
    components: tuple[FigureComponent, ...],
) -> tuple[FigureTextAssociation, ...]:
    page = detection_input.document.pages[plan.page_index]
    associations: list[FigureTextAssociation] = []
    used_blocks: set[str] = set()
    if plan.caption_block is not None:
        distance = min(
            visual.caption_distance
            for visual in plan.visuals
            if visual.caption_distance is not None
        )
        distance_text = _decimal(float(distance))
        retained_distance = float(distance_text)
        associations.append(
            FigureTextAssociation.create(
                role=FigureAssociationRole.CAPTION,
                page_index=plan.page_index,
                block=plan.caption_block,
                component_id=None,
                confidence=max(0.70, 1.0 - retained_distance / 720.0),
                evidence=(
                    ("method", "explicit_figure_prefix_and_geometry"),
                    ("distance_points", distance_text),
                ),
            )
        )
        used_blocks.add(plan.caption_block.block_id)
    for component in components:
        for block in page.blocks:
            if (
                block.kind != "text"
                or block.text is None
                or block.block_id in used_blocks
            ):
                continue
            box = _optional_block_box(block)
            if box is None:
                continue
            role: FigureAssociationRole | None = None
            if _SUBFIGURE_LABEL.match(block.text) and _near_box(
                box,
                component.source_bounding_box,
                detection_input.configuration.association_distance_points / 2.0,
            ):
                role = FigureAssociationRole.SUBFIGURE_LABEL
            elif (
                len(block.text)
                <= detection_input.configuration.maximum_legend_characters
                and _LEGEND.match(block.text)
                and _near_box(
                    box,
                    component.source_bounding_box,
                    detection_input.configuration.association_distance_points
                    / 4.0,
                )
            ):
                role = FigureAssociationRole.LEGEND
            if role is None:
                continue
            associations.append(
                FigureTextAssociation.create(
                    role=role,
                    page_index=plan.page_index,
                    block=block,
                    component_id=component.component_id,
                    confidence=(
                        0.88
                        if role is FigureAssociationRole.SUBFIGURE_LABEL
                        else 0.76
                    ),
                    evidence=(
                        ("method", "source_text_and_component_geometry"),
                    ),
                )
            )
            used_blocks.add(block.block_id)
    if len(associations) > detection_input.configuration.max_associations:
        raise FigureDetectionLimitError("associations exceed max_associations")
    return tuple(associations)


def _drawing_groups(
    drawings: tuple[FigureDrawingEvidence, ...],
    configuration: FigureDetectionConfiguration,
) -> tuple[tuple[FigureDrawingEvidence, ...], ...]:
    if not drawings:
        return ()
    gap = configuration.drawing_group_gap_points
    cell_size = max(gap, 1.0)
    spatial: dict[tuple[int, int], list[int]] = {}
    parents = list(range(len(drawings)))
    comparisons = 0

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[max(left_root, right_root)] = min(left_root, right_root)

    def cells_for(
        box: BoundingBox, *, padding: float
    ) -> tuple[tuple[int, int], ...]:
        x0, y0, x1, y1 = box
        first_x = math.floor((x0 - padding) / cell_size)
        last_x = math.floor((x1 + padding) / cell_size)
        first_y = math.floor((y0 - padding) / cell_size)
        last_y = math.floor((y1 + padding) / cell_size)
        return tuple(
            (x, y)
            for x in range(first_x, last_x + 1)
            for y in range(first_y, last_y + 1)
        )

    for index, drawing in enumerate(drawings):
        candidates = {
            prior
            for cell in cells_for(drawing.source_bounding_box, padding=0.0)
            for prior in spatial.get(cell, ())
        }
        touched_roots: set[int] = set()
        for prior in sorted(candidates):
            root = find(prior)
            if root in touched_roots:
                continue
            comparisons += 1
            if comparisons > configuration.max_drawing_group_comparisons:
                raise FigureDetectionLimitError(
                    "drawing grouping exceeds max_drawing_group_comparisons"
                )
            if _boxes_within(
                drawing.source_bounding_box,
                drawings[prior].source_bounding_box,
                gap,
            ):
                union(index, prior)
                touched_roots.add(root)
        for cell in cells_for(drawing.source_bounding_box, padding=gap):
            spatial.setdefault(cell, []).append(index)

    grouped: dict[int, list[FigureDrawingEvidence]] = {}
    for index, drawing in enumerate(drawings):
        grouped.setdefault(find(index), []).append(drawing)
    retained: list[tuple[FigureDrawingEvidence, ...]] = []
    for group in grouped.values():
        ordered = tuple(sorted(group, key=lambda item: item.source_object_id))
        box = _union_boxes_allowing_extents(
            tuple(item.source_bounding_box for item in ordered)
        )
        if (
            box[2] - box[0] < configuration.minimum_drawing_dimension_points
            or box[3] - box[1] < configuration.minimum_drawing_dimension_points
            or _box_area(box) < configuration.minimum_drawing_area_points
        ):
            continue
        retained.append(ordered)
    return tuple(retained)


def _nearest_caption(
    visual_box: BoundingBox,
    captions: tuple[ExtractedBlock, ...],
    configuration: FigureDetectionConfiguration,
) -> tuple[ExtractedBlock | None, float | None]:
    ranked: list[tuple[float, str, ExtractedBlock]] = []
    for caption in captions:
        box = _optional_block_box(caption)
        if box is None:
            continue
        vertical = _axis_gap(visual_box[1], visual_box[3], box[1], box[3])
        horizontal = _axis_gap(visual_box[0], visual_box[2], box[0], box[2])
        distance = vertical + horizontal * 0.5
        if distance <= configuration.association_distance_points:
            ranked.append((distance, caption.block_id, caption))
    if not ranked:
        return None, None
    ranked.sort(key=lambda value: (value[0], value[1]))
    return ranked[0][2], ranked[0][0]


def _materialize_warnings(
    candidates: tuple[FigureCandidate, ...],
    candidate_specs: tuple[list[_WarningSpec], ...],
    ignored_specs: tuple[_WarningSpec, ...],
) -> tuple[tuple[IngestionWarning, ...], tuple[FigureCandidate, ...]]:
    warnings: list[IngestionWarning] = []
    warning_ids_by_candidate: dict[str, list[str]] = {}
    for candidate, specs in zip(candidates, candidate_specs, strict=True):
        for spec in specs:
            warning = IngestionWarning.create(
                code=spec.code,
                severity=WarningSeverity.WARNING,
                message=spec.message,
                object_ids=(candidate.candidate_id,),
                source_spans=spec.source_spans,
                evidence=spec.evidence,
            )
            warnings.append(warning)
            warning_ids_by_candidate.setdefault(
                candidate.candidate_id, []
            ).append(warning.warning_id)
    for spec in ignored_specs:
        warnings.append(
            IngestionWarning.create(
                code=spec.code,
                severity=WarningSeverity.INFO,
                message=spec.message,
                source_spans=spec.source_spans,
                evidence=spec.evidence,
            )
        )
    final = tuple(
        replace(
            candidate,
            warning_ids=tuple(
                warning_ids_by_candidate.get(candidate.candidate_id, ())
            ),
        )
        for candidate in candidates
    )
    return tuple(warnings), final


def _validate_input_parts(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    page_evidence: tuple[FigurePageEvidence, ...],
    configuration: FigureDetectionConfiguration,
) -> None:
    if not isinstance(document, ExtractedDocument):
        raise TypeError("figure input document is unsupported")
    if not isinstance(configuration, FigureDetectionConfiguration):
        raise TypeError("figure configuration is unsupported")
    _require_tuple("figure layouts", layouts)
    _require_tuple("figure page evidence", page_evidence)
    if document.source.media_type != "application/pdf":
        raise ValueError("figure detection requires application/pdf")
    if document.source.byte_length > configuration.max_source_bytes:
        raise FigureDetectionLimitError("source exceeds max_source_bytes")
    if len(document.pages) > configuration.max_pages:
        raise FigureDetectionLimitError("pages exceed max_pages")
    if len(layouts) != len(document.pages) or len(page_evidence) != len(
        document.pages
    ):
        raise ValueError(
            "figure input requires one layout and page evidence per page"
        )
    block_count = sum(len(page.blocks) for page in document.pages)
    text_blocks = tuple(
        block
        for page in document.pages
        for block in page.blocks
        if block.kind == "text"
    )
    if block_count > configuration.max_input_blocks:
        raise FigureDetectionLimitError("blocks exceed max_input_blocks")
    if len(text_blocks) > configuration.max_text_blocks:
        raise FigureDetectionLimitError("text blocks exceed max_text_blocks")
    if (
        sum(len(block.text or "") for block in text_blocks)
        > configuration.max_text_characters
    ):
        raise FigureDetectionLimitError("text exceeds max_text_characters")
    span_count = sum(
        len(block.source_spans)
        for page in document.pages
        for block in page.blocks
    )
    if span_count > configuration.max_source_spans:
        raise FigureDetectionLimitError("source spans exceed max_source_spans")
    total_embedded_bytes = 0
    total_embedded_assets = 0
    total_drawings = 0
    for page, layout, evidence in zip(
        document.pages, layouts, page_evidence, strict=True
    ):
        if (
            layout.page_index != page.page_index
            or layout.source_id != document.source.source_id
            or layout.source_blob_id != document.source.blob_id
            or layout.source_content_hash != document.source.content_hash
            or layout.page_width != page.width
            or layout.page_height != page.height
            or layout.coordinate_system != page.coordinate_system
            or layout.rotation_degrees != page.rotation_degrees
            or layout.raw_block_ids
            != tuple(block.block_id for block in page.blocks)
            or layout.raw_blocks
            != tuple(
                LayoutBlockReference.from_block(block) for block in page.blocks
            )
        ):
            raise ValueError("figure layout evidence is stale or inconsistent")
        if (
            evidence.source_id != document.source.source_id
            or evidence.source_blob_id != document.source.blob_id
            or evidence.source_content_hash != document.source.content_hash
            or evidence.page_index != page.page_index
            or evidence.page_width != page.width
            or evidence.page_height != page.height
            or evidence.rotation_degrees != page.rotation_degrees
            or evidence.coordinate_system != page.coordinate_system
        ):
            raise ValueError("figure page evidence is stale or inconsistent")
        expected_image_ids = tuple(
            block.block_id for block in page.blocks if block.kind == "image"
        )
        if (
            tuple(
                artifact.source_block_id
                for artifact in evidence.embedded_artifacts
            )
            != expected_image_ids
        ):
            raise ValueError("figure embedded evidence is incomplete")
        block_by_id = {block.block_id: block for block in page.blocks}
        if len(
            {artifact.artifact_id for artifact in evidence.embedded_artifacts}
        ) != len(evidence.embedded_artifacts):
            raise ValueError("embedded artifact IDs must be unique")
        for artifact in evidence.embedded_artifacts:
            block = block_by_id[artifact.source_block_id]
            if (
                artifact.source_id != document.source.source_id
                or artifact.source_blob_id != document.source.blob_id
                or artifact.source_content_hash != document.source.content_hash
                or artifact.page_index != page.page_index
                or artifact.source_spans != block.source_spans
                or artifact.asset_id != block.asset_id
                or artifact.media_type != block.asset_media_type
                or artifact.mask_asset_id != block.asset_mask_id
                or artifact.mask_media_type != block.asset_mask_media_type
            ):
                raise ValueError(
                    "embedded artifact differs from raw image evidence"
                )
            if (
                artifact.byte_length > configuration.max_embedded_asset_bytes
                or (
                    artifact.mask_byte_length is not None
                    and artifact.mask_byte_length
                    > configuration.max_embedded_asset_bytes
                )
            ):
                raise FigureDetectionLimitError(
                    "embedded asset exceeds max_embedded_asset_bytes"
                )
            total_embedded_bytes += artifact.byte_length + (
                artifact.mask_byte_length or 0
            )
            total_embedded_assets += 1
        if len(evidence.drawings) > configuration.max_drawings_per_page:
            raise FigureDetectionLimitError(
                "retained drawings exceed their per-page limit"
            )
        if (
            len(evidence.drawings) + evidence.ignored_drawing_count
            > configuration.max_backend_drawings_per_page
        ):
            raise FigureDetectionLimitError(
                "backend drawings exceed their per-page limit"
            )
        if len({item.drawing_id for item in evidence.drawings}) != len(
            evidence.drawings
        ):
            raise ValueError("drawing evidence IDs must be unique")
        if (
            sum(item.item_count for item in evidence.drawings)
            > configuration.max_drawing_items_per_page
        ):
            raise FigureDetectionLimitError(
                "drawing items exceed max_drawing_items_per_page"
            )
        for drawing in evidence.drawings:
            if (
                drawing.source_id != document.source.source_id
                or drawing.source_blob_id != document.source.blob_id
                or drawing.page_index != page.page_index
                or not _box_within_page(drawing.source_bounding_box, page)
            ):
                raise ValueError("drawing evidence is stale or inconsistent")
        total_drawings += len(evidence.drawings)
    if total_embedded_assets > configuration.max_embedded_assets:
        raise FigureDetectionLimitError(
            "embedded assets exceed max_embedded_assets"
        )
    if total_embedded_bytes > configuration.max_total_embedded_bytes:
        raise FigureDetectionLimitError(
            "embedded assets exceed max_total_embedded_bytes"
        )
    if total_drawings > configuration.max_total_drawings:
        raise FigureDetectionLimitError("drawings exceed max_total_drawings")
    if span_count + total_drawings > configuration.max_source_spans:
        raise FigureDetectionLimitError("source spans exceed max_source_spans")


def _validate_result(result: FigureDetectionResult) -> None:
    if not isinstance(result.detection_input, FigureDetectionInput):
        raise TypeError("figure result input is unsupported")
    _require_tuple("figure candidates", result.candidates)
    _require_tuple("figure warnings", result.warnings)
    configuration = result.detection_input.configuration
    if result.configuration_digest != configuration.configuration_digest:
        raise ValueError("figure result configuration is inconsistent")
    _identity_fields(result.processor_name, result.processor_version)
    if len(result.candidates) > configuration.max_candidates:
        raise FigureDetectionLimitError("figures exceed max_candidates")
    if len(result.warnings) > configuration.max_warnings:
        raise FigureDetectionLimitError("warnings exceed max_warnings")
    warning_ids = tuple(warning.warning_id for warning in result.warnings)
    if len(set(warning_ids)) != len(warning_ids):
        raise ValueError("figure warnings must be unique")
    candidate_ids = {candidate.candidate_id for candidate in result.candidates}
    if len(candidate_ids) != len(result.candidates):
        raise ValueError("figure candidate IDs must be unique")
    component_ids = {
        component.component_id
        for candidate in result.candidates
        for component in candidate.components
    }
    if len(component_ids) != sum(
        len(candidate.components) for candidate in result.candidates
    ):
        raise ValueError("figure component IDs must be unique")
    allowed_objects = candidate_ids | component_ids
    for warning in result.warnings:
        if any(
            object_id not in allowed_objects for object_id in warning.object_ids
        ):
            raise ValueError("figure warning references an unknown object")
        if warning.object_ids:
            if warning.severity is not WarningSeverity.WARNING:
                raise ValueError(
                    "candidate figure warning severity is inconsistent"
                )
        elif (
            warning.severity is not WarningSeverity.INFO
            or warning.code
            not in (
                "figure.unassociated_drawing_ignored",
                "figure.caption_without_visual",
            )
        ):
            raise ValueError("figure informational warning is inconsistent")
    block_by_id = {
        block.block_id: block
        for page in result.detection_input.document.pages
        for block in page.blocks
    }
    artifact_by_id = {
        artifact.artifact_id: artifact
        for page in result.detection_input.page_evidence
        for artifact in page.embedded_artifacts
    }
    drawing_by_id = {
        drawing.drawing_id: drawing
        for page in result.detection_input.page_evidence
        for drawing in page.drawings
    }
    total_components = 0
    total_associations = 0
    for candidate in result.candidates:
        if (
            candidate.detection_input_id != result.detection_input.input_id
            or candidate.processor_name != result.processor_name
            or candidate.processor_version != result.processor_version
            or candidate.configuration_digest != result.configuration_digest
        ):
            raise ValueError(
                "figure candidate derivation evidence is inconsistent"
            )
        linked_warnings = tuple(
            warning
            for warning in result.warnings
            if candidate.candidate_id in warning.object_ids
        )
        expected_warning_ids = tuple(
            warning.warning_id for warning in linked_warnings
        )
        if candidate.warning_ids != expected_warning_ids:
            raise ValueError("figure candidate warning links are incomplete")
        if tuple(
            component.component_index for component in candidate.components
        ) != tuple(range(len(candidate.components))):
            raise ValueError("figure component indexes are not contiguous")
        expected_spans = tuple(
            span
            for component in candidate.components
            for span in component.source_spans
        )
        if candidate.source_spans != expected_spans:
            raise ValueError("figure candidate source spans are inconsistent")
        if candidate.source_bounding_box != _union_boxes(
            tuple(
                component.source_bounding_box
                for component in candidate.components
            )
        ):
            raise ValueError("figure candidate bounds are inconsistent")
        page = result.detection_input.document.pages[candidate.page_index]
        if not _box_within_page(candidate.source_bounding_box, page):
            raise ValueError("figure candidate bounds exceed its page")
        for component in candidate.components:
            expected_component_warning_ids = tuple(
                warning.warning_id
                for warning in result.warnings
                if component.component_id in warning.object_ids
            )
            if component.warning_ids != expected_component_warning_ids:
                raise ValueError(
                    "figure component warning links are incomplete"
                )
            if (
                component.detection_input_id != result.detection_input.input_id
                or component.page_index != candidate.page_index
                or component.processor_name != result.processor_name
                or component.processor_version != result.processor_version
                or component.configuration_digest != result.configuration_digest
            ):
                raise ValueError(
                    "figure component derivation evidence is inconsistent"
                )
            expected_component_confidence = (
                0.92
                if component.artifact_kind is FigureArtifactKind.EMBEDDED_IMAGE
                else 0.78
            )
            expected_component_evidence = (
                (
                    "method",
                    (
                        "embedded_image_bytes"
                        if component.artifact_kind
                        is FigureArtifactKind.EMBEDDED_IMAGE
                        else "rendered_pdf_drawing_commands"
                    ),
                ),
            )
            if (
                component.evidence_status is not FigureEvidenceStatus.PROPOSED
                or component.confidence != expected_component_confidence
                or component.evidence != expected_component_evidence
            ):
                raise ValueError("figure component proposal is inconsistent")
            if component.artifact_kind is FigureArtifactKind.EMBEDDED_IMAGE:
                artifact = artifact_by_id.get(
                    component.embedded_artifact_id or ""
                )
                if (
                    artifact is None
                    or component.source_block_ids != (artifact.source_block_id,)
                    or component.source_spans != artifact.source_spans
                    or component.source_bounding_box
                    != artifact.source_bounding_box
                ):
                    raise ValueError(
                        "embedded figure component is inconsistent"
                    )
            else:
                drawings = tuple(
                    drawing_by_id[item]
                    for item in component.drawing_evidence_ids
                )
                if component.source_spans != tuple(
                    drawing.source_span for drawing in drawings
                ):
                    raise ValueError(
                        "drawing component source spans are inconsistent"
                    )
                if component.source_bounding_box != _union_boxes(
                    tuple(drawing.source_bounding_box for drawing in drawings)
                ):
                    raise ValueError(
                        "drawing component bounds are inconsistent"
                    )
                _validate_component_render(
                    component, result.detection_input.document
                )
        component_id_set = {item.component_id for item in candidate.components}
        caption_associations = tuple(
            association
            for association in candidate.associations
            if association.role is FigureAssociationRole.CAPTION
        )
        if len(caption_associations) > 1:
            raise ValueError("figure candidate has multiple captions")
        expected_label = (
            _source_label(caption_associations[0].text)
            if caption_associations
            else None
        )
        if candidate.source_label != expected_label:
            raise ValueError("figure candidate source label is inconsistent")
        expected_confidence = min(
            component.confidence for component in candidate.components
        )
        if caption_associations:
            expected_confidence = min(1.0, expected_confidence + 0.08)
        else:
            expected_confidence = max(0.0, expected_confidence - 0.25)
        expected_warning_codes: list[str] = []
        if not caption_associations:
            expected_warning_codes.append("figure.caption_missing")
        if expected_confidence < configuration.proposed_confidence_threshold:
            expected_warning_codes.append("figure.low_confidence")
        expected_status = (
            FigureEvidenceStatus.AMBIGUOUS
            if expected_warning_codes
            else FigureEvidenceStatus.PROPOSED
        )
        if (
            candidate.confidence != expected_confidence
            or candidate.evidence_status is not expected_status
            or candidate.evidence
            != (
                ("component_count", str(len(candidate.components))),
                (
                    "caption_present",
                    str(bool(caption_associations)).lower(),
                ),
            )
            or [warning.code for warning in linked_warnings]
            != expected_warning_codes
        ):
            raise ValueError("figure candidate proposal is inconsistent")
        if len({item.block_id for item in candidate.associations}) != len(
            candidate.associations
        ):
            raise ValueError("figure association blocks must be unique")
        for association in candidate.associations:
            block = block_by_id.get(association.block_id)
            if (
                block is None
                or block.text != association.text
                or block.source_spans != association.source_spans
                or association.page_index != candidate.page_index
                or (
                    association.component_id is not None
                    and association.component_id not in component_id_set
                )
            ):
                raise ValueError(
                    "figure association source evidence is inconsistent"
                )
            if association.role is FigureAssociationRole.CAPTION:
                if (
                    association.component_id is not None
                    or _FIGURE_CAPTION.match(association.text) is None
                    or len(association.evidence) != 2
                    or association.evidence[0]
                    != (
                        "method",
                        "explicit_figure_prefix_and_geometry",
                    )
                    or association.evidence[1][0] != "distance_points"
                ):
                    raise ValueError(
                        "figure caption association is inconsistent"
                    )
                caption_box = _block_box(block)
                exact_distance = min(
                    _axis_gap(
                        component.source_bounding_box[1],
                        component.source_bounding_box[3],
                        caption_box[1],
                        caption_box[3],
                    )
                    + _axis_gap(
                        component.source_bounding_box[0],
                        component.source_bounding_box[2],
                        caption_box[0],
                        caption_box[2],
                    )
                    * 0.5
                    for component in candidate.components
                )
                expected_distance_text = _decimal(exact_distance)
                try:
                    distance = float(association.evidence[1][1])
                except ValueError as error:
                    raise ValueError(
                        "figure caption distance is inconsistent"
                    ) from error
                if (
                    association.evidence[1][1] != expected_distance_text
                    or not 0.0
                    <= distance
                    <= configuration.association_distance_points
                    or association.confidence
                    != max(0.70, 1.0 - distance / 720.0)
                ):
                    raise ValueError(
                        "figure caption confidence is inconsistent"
                    )
            elif association.role is FigureAssociationRole.SUBFIGURE_LABEL:
                if (
                    association.component_id is None
                    or _SUBFIGURE_LABEL.match(association.text) is None
                    or association.confidence != 0.88
                    or association.evidence
                    != (("method", "source_text_and_component_geometry"),)
                    or not _near_box(
                        _block_box(block),
                        next(
                            component.source_bounding_box
                            for component in candidate.components
                            if component.component_id
                            == association.component_id
                        ),
                        configuration.association_distance_points / 2.0,
                    )
                ):
                    raise ValueError(
                        "subfigure-label association is inconsistent"
                    )
            elif (
                association.component_id is None
                or _LEGEND.match(association.text) is None
                or association.confidence != 0.76
                or association.evidence
                != (("method", "source_text_and_component_geometry"),)
                or not _near_box(
                    _block_box(block),
                    next(
                        component.source_bounding_box
                        for component in candidate.components
                        if component.component_id == association.component_id
                    ),
                    configuration.association_distance_points / 4.0,
                )
            ):
                raise ValueError("figure legend association is inconsistent")
        total_components += len(candidate.components)
        total_associations += len(candidate.associations)
    if total_components > configuration.max_components:
        raise FigureDetectionLimitError("components exceed max_components")
    if total_associations > configuration.max_associations:
        raise FigureDetectionLimitError("associations exceed max_associations")
    _validate_retained_size(result, configuration.max_result_bytes)


def _validate_component_render(
    component: FigureComponent,
    document: ExtractedDocument,
) -> None:
    region = component.rendered_region
    if region is None:
        raise ValueError("drawing component lacks rendered evidence")
    page = document.pages[component.page_index]
    if (
        region.source_id != document.source.source_id
        or region.source_blob_id != document.source.blob_id
        or region.source_content_hash != document.source.content_hash
        or region.page_index != component.page_index
        or region.coordinate_system != page.coordinate_system
        or region.page_rotation_degrees != page.rotation_degrees
        or region.selection_was_full_page
    ):
        raise ValueError("drawing render provenance is inconsistent")
    rx0, ry0, rx1, ry1 = region.source_bounding_box
    x0, y0, x1, y1 = component.source_bounding_box
    if rx0 > x0 or ry0 > y0 or rx1 < x1 or ry1 < y1:
        raise ValueError("drawing render does not contain component bounds")


def _validate_rendered_aggregate(
    regions: tuple[RenderedRegion, ...],
    configuration: FigureDetectionConfiguration,
) -> None:
    png_bytes = sum(region.byte_length for region in regions)
    pixels = sum(
        region.width_pixels * region.height_pixels for region in regions
    )
    if png_bytes > configuration.max_total_rendered_png_bytes:
        raise FigureDetectionLimitError(
            "rendered PNGs exceed max_total_rendered_png_bytes"
        )
    if pixels > configuration.max_total_rendered_pixels:
        raise FigureDetectionLimitError(
            "rendered regions exceed max_total_rendered_pixels"
        )


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


def _raw_image_media_type(raw_block: dict[str, object]) -> str:
    extension = str(raw_block.get("ext", "")).strip().lower()
    return {
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "jpx": "image/jp2",
        "png": "image/png",
        "tif": "image/tiff",
        "tiff": "image/tiff",
    }.get(
        extension,
        f"image/{extension}" if extension else "application/octet-stream",
    )


def _detect_media_type(payload: bytes) -> str:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if payload.startswith(b"\x00\x00\x00\x0cjP  \r\n\x87\n"):
        return "image/jp2"
    return "application/octet-stream"


def _source_label(text: str) -> str | None:
    match = _FIGURE_CAPTION.match(text)
    if match is None:
        return None
    prefix = match.group("prefix")
    label = (match.group("label") or "").strip()
    subfigure = (match.group("subfigure") or "").strip()
    suffix = f"{label}{subfigure}"
    return f"{prefix} {suffix}" if suffix else prefix


def _verify_page_geometry(page: Any, extracted_page: ExtractedPage) -> None:
    if (
        float(page.cropbox.width) != extracted_page.width
        or float(page.cropbox.height) != extracted_page.height
        or int(page.rotation) != extracted_page.rotation_degrees
    ):
        raise ValueError("PDF page geometry does not match extracted document")


def _read_exact_payload(
    source: SourceDocument,
    content: BinaryIO,
    configuration: FigureDetectionConfiguration,
) -> bytes:
    if source.media_type != "application/pdf":
        raise ValueError("figure detection requires application/pdf")
    if source.byte_length > configuration.max_source_bytes:
        raise FigureDetectionLimitError("source exceeds max_source_bytes")
    payload = content.read(configuration.max_source_bytes + 1)
    if not isinstance(payload, bytes):
        raise TypeError("PDF content stream must return bytes")
    if len(payload) > configuration.max_source_bytes:
        raise FigureDetectionLimitError("source exceeds max_source_bytes")
    if len(payload) != source.byte_length:
        raise ValueError("PDF content length does not match source identity")
    if hashlib.sha256(payload).hexdigest() != source.content_hash:
        raise ValueError("PDF content hash does not match source identity")
    return payload


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
                if field.name in (
                    "content",
                    "mask_content",
                ) and item.__class__.__name__ in (
                    "RenderedRegion",
                    "EmbeddedFigureArtifact",
                ):
                    continue
                stack.append(getattr(item, field.name))
        else:
            raise TypeError("figure result contains unsupported evidence")
        if total > limit:
            raise FigureDetectionLimitError(
                "figure detection result exceeds max_result_bytes"
            )

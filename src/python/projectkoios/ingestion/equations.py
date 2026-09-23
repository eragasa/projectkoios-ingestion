from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, fields, is_dataclass, replace
from enum import Enum, StrEnum
from typing import BinaryIO, Protocol

from projectkoios.ingestion.base import BaseEquationCandidateDetector
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

EQUATION_CONTRACT_VERSION = "1.0"
EQUATION_DETECTOR_VERSION = "1"
_MAX_PAGES = 512
_MAX_INPUT_BLOCKS = 16_384
_MAX_TEXT_BLOCKS = 8_192
_MAX_TEXT_CHARACTERS = 5_000_000
_MAX_INPUT_SOURCE_SPANS = 16_384
_MAX_CANDIDATES = 256
_MAX_INLINE_CANDIDATES_PER_BLOCK = 8
_MAX_CANDIDATE_TEXT_CHARACTERS = 4_096
_MAX_WARNINGS = 4_096
_MAX_RESULT_BYTES = 128_000_000
_MAX_TOTAL_RENDERED_PNG_BYTES = 100_000_000
_MAX_TOTAL_RENDERED_PIXELS = 25_000_000
_MAX_IDENTITY_CHARACTERS = 4_096
_MAX_METADATA_CHARACTERS = 100_000
_MAX_SOURCE_SPANS = 2_048
_TRAILING_LABEL = re.compile(
    r"(?P<label>\(\s*[A-Za-z]?\d+(?:\.\d+)*[A-Za-z]?\s*\)"
    r"|\[\s*[A-Za-z]?\d+(?:\.\d+)*[A-Za-z]?\s*\])\s*$"
)
_DELIMITED_INLINE = re.compile(
    r"(?P<dollar>\$(?!\$)(?P<dollar_body>[^$\n]{1,256})\$)"
    r"|(?P<paren>\\\((?P<paren_body>.{1,256}?)\\\))"
)
_RELATIONAL_INLINE = re.compile(
    r"(?<![\w])(?P<body>[A-Za-zΑ-ω]\s*"
    r"(?:=|≈|≃|≤|≥|≠|∝)\s*[^,;:.\n]{1,120})"
)
_RELATIONS = frozenset("=≈≃≤≥≠∝")
_OPERATORS = frozenset("+-−×÷/^_∑∫√∂∇∞±→←∏⋅·")
_STRONG_MATH = frozenset("∑∫√∂∇∞∏")
_GREEK_RANGE = re.compile(r"[Α-Ͽ]")
_VARIABLE_TOKEN = re.compile(r"(?<!\w)[A-Za-zΑ-ω](?!\w)")
_LATEX_COMMAND = re.compile(r"\\[A-Za-z]{2,}")


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


class EquationDetectionLimitError(ValueError):
    """Raised before equation detection exceeds a configured hard bound."""


class EquationCandidateKind(StrEnum):
    DISPLAY = "display"
    INLINE = "inline"


class EquationEvidenceStatus(StrEnum):
    """A candidate status with no accepted or validated state."""

    PROPOSED = "proposed"
    AMBIGUOUS = "ambiguous"


class EquationContextDirection(StrEnum):
    PRECEDING = "preceding"
    FOLLOWING = "following"


@dataclass(frozen=True)
class EquationDetectionConfiguration:
    max_pages: int = _MAX_PAGES
    max_input_blocks: int = _MAX_INPUT_BLOCKS
    max_text_blocks: int = _MAX_TEXT_BLOCKS
    max_text_characters: int = _MAX_TEXT_CHARACTERS
    max_input_source_spans: int = _MAX_INPUT_SOURCE_SPANS
    max_candidates: int = _MAX_CANDIDATES
    max_inline_candidates_per_block: int = _MAX_INLINE_CANDIDATES_PER_BLOCK
    max_candidate_text_characters: int = _MAX_CANDIDATE_TEXT_CHARACTERS
    max_warnings: int = _MAX_WARNINGS
    max_result_bytes: int = _MAX_RESULT_BYTES
    max_total_rendered_png_bytes: int = _MAX_TOTAL_RENDERED_PNG_BYTES
    max_total_rendered_pixels: int = _MAX_TOTAL_RENDERED_PIXELS
    render_padding_points: float = 6.0
    ambiguous_confidence_threshold: float = 0.75

    def __post_init__(self) -> None:
        for name, hard_maximum in (
            ("max_pages", _MAX_PAGES),
            ("max_input_blocks", _MAX_INPUT_BLOCKS),
            ("max_text_blocks", _MAX_TEXT_BLOCKS),
            ("max_text_characters", _MAX_TEXT_CHARACTERS),
            ("max_input_source_spans", _MAX_INPUT_SOURCE_SPANS),
            ("max_candidates", _MAX_CANDIDATES),
            (
                "max_inline_candidates_per_block",
                _MAX_INLINE_CANDIDATES_PER_BLOCK,
            ),
            (
                "max_candidate_text_characters",
                _MAX_CANDIDATE_TEXT_CHARACTERS,
            ),
            ("max_warnings", _MAX_WARNINGS),
            ("max_result_bytes", _MAX_RESULT_BYTES),
            (
                "max_total_rendered_png_bytes",
                _MAX_TOTAL_RENDERED_PNG_BYTES,
            ),
            ("max_total_rendered_pixels", _MAX_TOTAL_RENDERED_PIXELS),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer")
            if value > hard_maximum:
                raise EquationDetectionLimitError(
                    f"{name} exceeds the implementation maximum "
                    f"({hard_maximum})"
                )
        padding = _finite_float(
            "render_padding_points", self.render_padding_points
        )
        if padding < 0.0 or padding > 72.0:
            raise ValueError(
                "render_padding_points must be between zero and 72"
            )
        object.__setattr__(self, "render_padding_points", padding)
        threshold = _unit_float(
            "ambiguous_confidence_threshold",
            self.ambiguous_confidence_threshold,
        )
        object.__setattr__(self, "ambiguous_confidence_threshold", threshold)

    @property
    def configuration_digest(self) -> str:
        return stable_id(
            "equation-detection-configuration",
            self.identity_parts(),
        )

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.max_pages,
            self.max_input_blocks,
            self.max_text_blocks,
            self.max_text_characters,
            self.max_input_source_spans,
            self.max_candidates,
            self.max_inline_candidates_per_block,
            self.max_candidate_text_characters,
            self.max_warnings,
            self.max_result_bytes,
            self.max_total_rendered_png_bytes,
            self.max_total_rendered_pixels,
            self.render_padding_points,
            self.ambiguous_confidence_threshold,
        )


@dataclass(frozen=True)
class EquationContextReference:
    context_id: str
    direction: EquationContextDirection
    block_id: str
    source_spans: tuple[SourceSpan, ...]

    @classmethod
    def create(
        cls,
        *,
        direction: EquationContextDirection,
        block: ExtractedBlock,
    ) -> EquationContextReference:
        if not isinstance(direction, EquationContextDirection):
            raise TypeError("direction must be EquationContextDirection")
        _bounded_string("context block ID", block.block_id)
        _validate_spans(block.source_spans)
        context_id = _context_id(direction, block.block_id, block.source_spans)
        return cls(
            context_id=context_id,
            direction=direction,
            block_id=block.block_id,
            source_spans=block.source_spans,
        )

    def __post_init__(self) -> None:
        _bounded_string("context ID", self.context_id)
        if not isinstance(self.direction, EquationContextDirection):
            raise TypeError("direction must be EquationContextDirection")
        _bounded_string("context block ID", self.block_id)
        _validate_spans(self.source_spans)
        if self.context_id != _context_id(
            self.direction, self.block_id, self.source_spans
        ):
            raise ValueError("equation context ID is inconsistent")


@dataclass(frozen=True)
class EquationDetectionInput:
    input_id: str
    document: ExtractedDocument
    layouts: tuple[PageLayoutResult, ...]
    configuration: EquationDetectionConfiguration
    contract_version: str = EQUATION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        document: ExtractedDocument,
        layouts: tuple[PageLayoutResult, ...],
        configuration: EquationDetectionConfiguration | None = None,
    ) -> EquationDetectionInput:
        actual = configuration or EquationDetectionConfiguration()
        _validate_input_parts(document, layouts, actual)
        return cls(
            input_id=_input_id(document, layouts, actual),
            document=document,
            layouts=layouts,
            configuration=actual,
        )

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_CONTRACT_VERSION:
            raise ValueError("unsupported equation detection input version")
        _bounded_string("equation detection input ID", self.input_id)
        _validate_input_parts(self.document, self.layouts, self.configuration)
        if self.input_id != _input_id(
            self.document, self.layouts, self.configuration
        ):
            raise ValueError("equation detection input ID is inconsistent")


@dataclass(frozen=True)
class EquationCandidate:
    candidate_id: str
    detection_input_id: str
    kind: EquationCandidateKind
    source_block_id: str
    source_spans: tuple[SourceSpan, ...]
    raw_text: str
    source_label: str | None
    rendered_region: RenderedRegion
    preceding_context: EquationContextReference | None
    following_context: EquationContextReference | None
    confidence: float
    evidence_status: EquationEvidenceStatus
    evidence: Metadata
    warning_ids: tuple[str, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = EQUATION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        detection_input_id: str,
        kind: EquationCandidateKind,
        source_block_id: str,
        source_spans: tuple[SourceSpan, ...],
        raw_text: str,
        source_label: str | None,
        rendered_region: RenderedRegion,
        preceding_context: EquationContextReference | None,
        following_context: EquationContextReference | None,
        confidence: float,
        evidence_status: EquationEvidenceStatus,
        evidence: Metadata,
        warning_ids: tuple[str, ...],
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> EquationCandidate:
        normalized_confidence = _unit_float("confidence", confidence)
        _validate_candidate_parts(
            detection_input_id=detection_input_id,
            kind=kind,
            source_block_id=source_block_id,
            source_spans=source_spans,
            raw_text=raw_text,
            source_label=source_label,
            rendered_region=rendered_region,
            preceding_context=preceding_context,
            following_context=following_context,
            confidence=normalized_confidence,
            evidence_status=evidence_status,
            evidence=evidence,
            warning_ids=warning_ids,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )
        candidate_id = _candidate_id(
            detection_input_id=detection_input_id,
            kind=kind,
            source_block_id=source_block_id,
            source_spans=source_spans,
            raw_text=raw_text,
            source_label=source_label,
            rendered_region_id=rendered_region.region_id,
            preceding_context_id=(
                preceding_context.context_id
                if preceding_context is not None
                else None
            ),
            following_context_id=(
                following_context.context_id
                if following_context is not None
                else None
            ),
            confidence=normalized_confidence,
            evidence_status=evidence_status,
            evidence=evidence,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )
        return cls(
            candidate_id=candidate_id,
            detection_input_id=detection_input_id,
            kind=kind,
            source_block_id=source_block_id,
            source_spans=source_spans,
            raw_text=raw_text,
            source_label=source_label,
            rendered_region=rendered_region,
            preceding_context=preceding_context,
            following_context=following_context,
            confidence=normalized_confidence,
            evidence_status=evidence_status,
            evidence=evidence,
            warning_ids=warning_ids,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_CONTRACT_VERSION:
            raise ValueError("unsupported equation candidate version")
        object.__setattr__(
            self, "confidence", _unit_float("confidence", self.confidence)
        )
        _bounded_string("candidate ID", self.candidate_id)
        _validate_candidate_parts(
            detection_input_id=self.detection_input_id,
            kind=self.kind,
            source_block_id=self.source_block_id,
            source_spans=self.source_spans,
            raw_text=self.raw_text,
            source_label=self.source_label,
            rendered_region=self.rendered_region,
            preceding_context=self.preceding_context,
            following_context=self.following_context,
            confidence=self.confidence,
            evidence_status=self.evidence_status,
            evidence=self.evidence,
            warning_ids=self.warning_ids,
            processor_name=self.processor_name,
            processor_version=self.processor_version,
            configuration_digest=self.configuration_digest,
        )
        expected = _candidate_id(
            detection_input_id=self.detection_input_id,
            kind=self.kind,
            source_block_id=self.source_block_id,
            source_spans=self.source_spans,
            raw_text=self.raw_text,
            source_label=self.source_label,
            rendered_region_id=self.rendered_region.region_id,
            preceding_context_id=(
                self.preceding_context.context_id
                if self.preceding_context is not None
                else None
            ),
            following_context_id=(
                self.following_context.context_id
                if self.following_context is not None
                else None
            ),
            confidence=self.confidence,
            evidence_status=self.evidence_status,
            evidence=self.evidence,
            processor_name=self.processor_name,
            processor_version=self.processor_version,
            configuration_digest=self.configuration_digest,
        )
        if self.candidate_id != expected:
            raise ValueError("equation candidate ID is inconsistent")


@dataclass(frozen=True)
class EquationDetectionResult:
    result_id: str
    detection_input: EquationDetectionInput
    candidates: tuple[EquationCandidate, ...]
    warnings: tuple[IngestionWarning, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = EQUATION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        detection_input: EquationDetectionInput,
        candidates: tuple[EquationCandidate, ...],
        warnings: tuple[IngestionWarning, ...],
        processor_name: str,
        processor_version: str,
    ) -> EquationDetectionResult:
        if not isinstance(detection_input, EquationDetectionInput):
            raise TypeError("detection_input must be EquationDetectionInput")
        _preflight_result(detection_input, candidates, warnings)
        _bounded_string("processor_name", processor_name)
        _bounded_string("processor_version", processor_version)
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
        result_id = _result_id(
            detection_input.input_id,
            candidates,
            warnings,
            processor_name,
            processor_version,
            digest,
        )
        return cls(
            result_id=result_id,
            detection_input=detection_input,
            candidates=candidates,
            warnings=warnings,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_CONTRACT_VERSION:
            raise ValueError("unsupported equation detection result version")
        if not isinstance(self.detection_input, EquationDetectionInput):
            raise TypeError("detection_input must be EquationDetectionInput")
        _bounded_string("equation result ID", self.result_id)
        _preflight_result(self.detection_input, self.candidates, self.warnings)
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
            raise ValueError("equation detection result ID is inconsistent")


@dataclass(frozen=True)
class _OrderedBlock:
    block: ExtractedBlock
    page_width: float
    page_height: float
    reading_order: int
    layout_confidence: float


@dataclass(frozen=True)
class _ProvisionalCandidate:
    key: str
    kind: EquationCandidateKind
    block: ExtractedBlock
    source_spans: tuple[SourceSpan, ...]
    raw_text: str
    source_label: str | None
    selection: PageRegionSelection
    preceding_context: EquationContextReference | None
    following_context: EquationContextReference | None
    confidence: float
    evidence_status: EquationEvidenceStatus
    evidence: Metadata
    warning_code: str | None


class DeterministicEquationCandidateDetector(BaseEquationCandidateDetector):
    """Detect and render bounded equation-shaped source evidence."""

    name = "deterministic-equation-candidate-detector"
    version = EQUATION_DETECTOR_VERSION

    def __init__(
        self,
        configuration: EquationDetectionConfiguration | None = None,
        *,
        layout_processor: _PageLayoutProcessor | None = None,
        region_renderer: _PageRegionRenderer | None = None,
    ) -> None:
        self.configuration = configuration or EquationDetectionConfiguration()
        self.layout_processor = (
            layout_processor or DeterministicLayoutProcessor()
        )
        self.region_renderer = region_renderer or PyMuPdfRegionRenderer()

    @property
    def configuration_digest(self) -> str:
        return self.configuration.configuration_digest

    def detect(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
    ) -> EquationDetectionResult:
        layouts = self.layout_processor.analyze(document)
        return self.detect_with_layout(document, content, layouts)

    def detect_with_layout(
        self,
        document: ExtractedDocument,
        content: BinaryIO,
        layouts: tuple[PageLayoutResult, ...],
    ) -> EquationDetectionResult:
        detection_input = EquationDetectionInput.create(
            document=document,
            layouts=layouts,
            configuration=self.configuration,
        )
        ordered = _ordered_blocks(detection_input)
        provisional, warning_specs = _detect_candidates(
            detection_input, ordered
        )
        if len(provisional) > self.configuration.max_candidates:
            raise EquationDetectionLimitError(
                "equation candidates exceed max_candidates"
            )
        rendered_by_selection: dict[PageRegionSelection, RenderedRegion] = {}
        if provisional:
            rendered = self.region_renderer.render(
                document.source,
                content,
                tuple(item.selection for item in provisional),
            )
            for selection, region in zip(
                (item.selection for item in provisional),
                rendered,
                strict=True,
            ):
                previous = rendered_by_selection.get(selection)
                if previous is not None and previous != region:
                    raise ValueError(
                        "renderer returned inconsistent duplicate selections"
                    )
                rendered_by_selection[selection] = region
            _validate_rendered_aggregate(
                tuple(rendered_by_selection.values()),
                self.configuration,
            )
        base_candidates = tuple(
            EquationCandidate.create(
                detection_input_id=detection_input.input_id,
                kind=item.kind,
                source_block_id=item.block.block_id,
                source_spans=item.source_spans,
                raw_text=item.raw_text,
                source_label=item.source_label,
                rendered_region=rendered_by_selection[item.selection],
                preceding_context=item.preceding_context,
                following_context=item.following_context,
                confidence=item.confidence,
                evidence_status=item.evidence_status,
                evidence=item.evidence,
                warning_ids=(),
                processor_name=self.name,
                processor_version=self.version,
                configuration_digest=self.configuration_digest,
            )
            for item in provisional
        )
        candidate_by_key = {
            item.key: candidate
            for item, candidate in zip(
                provisional, base_candidates, strict=True
            )
        }
        warnings = _materialize_warnings(
            warning_specs,
            candidate_by_key,
        )
        warning_ids_by_candidate: dict[str, list[str]] = {}
        for warning in warnings:
            for object_id in warning.object_ids:
                if object_id in {
                    candidate.candidate_id for candidate in base_candidates
                }:
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
        return EquationDetectionResult.create(
            detection_input=detection_input,
            candidates=candidates,
            warnings=warnings,
            processor_name=self.name,
            processor_version=self.version,
        )


@dataclass(frozen=True)
class _WarningSpec:
    code: str
    message: str
    object_ids: tuple[str, ...]
    candidate_keys: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    evidence: Metadata = ()


def _validate_input_parts(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    configuration: EquationDetectionConfiguration,
) -> None:
    if not isinstance(document, ExtractedDocument):
        raise TypeError("document must be ExtractedDocument")
    if not isinstance(layouts, tuple):
        raise TypeError("layouts must be an immutable tuple")
    if not isinstance(configuration, EquationDetectionConfiguration):
        raise TypeError("configuration has the wrong type")
    if len(document.pages) > configuration.max_pages:
        raise EquationDetectionLimitError("document pages exceed max_pages")
    if len(layouts) != len(document.pages):
        raise ValueError("one layout result is required per document page")
    total_input_blocks = 0
    total_text_blocks = 0
    total_text_characters = 0
    total_source_spans = 0
    block_ids: set[str] = set()
    for page, layout in zip(document.pages, layouts, strict=True):
        if not isinstance(layout, PageLayoutResult):
            raise TypeError("layouts must contain PageLayoutResult values")
        if (
            layout.source_id != document.source.source_id
            or layout.source_blob_id != document.source.blob_id
            or layout.source_content_hash != document.source.content_hash
            or layout.page_index != page.page_index
            or layout.page_width != page.width
            or layout.page_height != page.height
            or layout.coordinate_system != page.coordinate_system
            or layout.rotation_degrees != page.rotation_degrees
        ):
            raise ValueError("layout result does not match its document page")
        expected_raw = tuple(
            (block.block_id, block.kind, block.source_spans)
            for block in page.blocks
        )
        actual_raw = tuple(
            (item.block_id, item.kind, item.source_spans)
            for item in layout.raw_blocks
        )
        if expected_raw != actual_raw:
            raise ValueError("layout raw blocks do not match the document page")
        total_input_blocks += len(page.blocks)
        if total_input_blocks > configuration.max_input_blocks:
            raise EquationDetectionLimitError(
                "input blocks exceed max_input_blocks"
            )
        for block in page.blocks:
            total_source_spans += len(block.source_spans)
            if total_source_spans > configuration.max_input_source_spans:
                raise EquationDetectionLimitError(
                    "input source spans exceed max_input_source_spans"
                )
            if block.block_id in block_ids:
                raise ValueError("document block IDs must be globally unique")
            block_ids.add(block.block_id)
            if block.kind == "text" and isinstance(block.text, str):
                total_text_blocks += 1
                total_text_characters += len(block.text)
                if total_text_blocks > configuration.max_text_blocks:
                    raise EquationDetectionLimitError(
                        "text blocks exceed max_text_blocks"
                    )
                if total_text_characters > configuration.max_text_characters:
                    raise EquationDetectionLimitError(
                        "text exceeds max_text_characters"
                    )


def _input_id(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    configuration: EquationDetectionConfiguration,
) -> str:
    return stable_id(
        "equation-detection-input",
        EQUATION_CONTRACT_VERSION,
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
        configuration.identity_parts(),
    )


def _ordered_blocks(
    detection_input: EquationDetectionInput,
) -> tuple[_OrderedBlock, ...]:
    values: list[_OrderedBlock] = []
    for page, layout in zip(
        detection_input.document.pages,
        detection_input.layouts,
        strict=True,
    ):
        blocks = {block.block_id: block for block in page.blocks}
        proposed = set(layout.proposed_order)
        ordered_ids = list(layout.proposed_order)
        ordered_ids.extend(
            block.block_id
            for block in page.blocks
            if block.kind == "text" and block.block_id not in proposed
        )
        for block_id in ordered_ids:
            block = blocks[block_id]
            if not isinstance(block.text, str) or not block.text.strip():
                continue
            values.append(
                _OrderedBlock(
                    block=block,
                    page_width=page.width,
                    page_height=page.height,
                    reading_order=len(values),
                    layout_confidence=(
                        layout.confidence if block_id in proposed else 0.35
                    ),
                )
            )
    return tuple(values)


def _detect_candidates(
    detection_input: EquationDetectionInput,
    ordered: tuple[_OrderedBlock, ...],
) -> tuple[list[_ProvisionalCandidate], list[_WarningSpec]]:
    config = detection_input.configuration
    provisional: list[_ProvisionalCandidate] = []
    warnings: list[_WarningSpec] = []
    for index, item in enumerate(ordered):
        text = item.block.text
        if text is None:
            raise ValueError("ordered equation text block has no text")
        display = _display_evidence(text, item, config)
        if display is not None:
            box = _block_box(item.block.source_spans)
            if box is None:
                warnings.append(
                    _WarningSpec(
                        code="equation.missing_geometry",
                        message=(
                            "Equation-shaped display text has no renderable "
                            "source geometry"
                        ),
                        object_ids=(item.block.block_id,),
                        candidate_keys=(),
                        source_spans=item.block.source_spans,
                    )
                )
                continue
            candidate = _provisional_display(
                detection_input,
                ordered,
                index,
                item,
                display,
                box,
            )
            provisional.append(candidate)
            if candidate.warning_code is not None:
                warnings.append(_candidate_warning_spec(candidate))
        else:
            inline = _inline_evidence(text, config)
            if len(inline) > config.max_inline_candidates_per_block:
                raise EquationDetectionLimitError(
                    "inline candidates exceed their per-block limit"
                )
            for inline_index, (start, end, method, confidence) in enumerate(
                inline
            ):
                if len(item.block.source_spans) != 1:
                    warnings.append(
                        _WarningSpec(
                            code="equation.inline_offsets_ambiguous",
                            message=(
                                "Inline equation offsets cannot be mapped "
                                "across multiple source spans"
                            ),
                            object_ids=(item.block.block_id,),
                            candidate_keys=(),
                            source_spans=item.block.source_spans,
                        )
                    )
                    break
                box = _block_box(item.block.source_spans)
                if box is None:
                    warnings.append(
                        _WarningSpec(
                            code="equation.missing_geometry",
                            message=(
                                "Inline equation-shaped text has no renderable "
                                "source geometry"
                            ),
                            object_ids=(item.block.block_id,),
                            candidate_keys=(),
                            source_spans=item.block.source_spans,
                        )
                    )
                    break
                candidate = _provisional_inline(
                    detection_input,
                    ordered,
                    index,
                    item,
                    inline_index,
                    start,
                    end,
                    method,
                    confidence,
                    box,
                )
                provisional.append(candidate)
                if candidate.warning_code is not None:
                    warnings.append(_candidate_warning_spec(candidate))
        if len(provisional) > config.max_candidates:
            raise EquationDetectionLimitError(
                "equation candidates exceed max_candidates"
            )
        if len(warnings) > config.max_warnings:
            raise EquationDetectionLimitError("warnings exceed max_warnings")
    if len(warnings) > config.max_warnings:
        raise EquationDetectionLimitError("warnings exceed max_warnings")
    return provisional, warnings


def _display_evidence(
    text: str,
    item: _OrderedBlock,
    configuration: EquationDetectionConfiguration,
) -> tuple[float, Metadata, str | None] | None:
    stripped = text.strip()
    if (
        not stripped
        or len(stripped) > configuration.max_candidate_text_characters
        or len(stripped.splitlines()) > 3
    ):
        return None
    if _DELIMITED_INLINE.search(stripped) is not None:
        return None
    label_match = _TRAILING_LABEL.search(stripped)
    label = label_match.group("label") if label_match is not None else None
    expression = (
        stripped[: label_match.start()].rstrip()
        if label_match is not None
        else stripped
    )
    relation_count = sum(character in _RELATIONS for character in expression)
    operator_count = sum(character in _OPERATORS for character in expression)
    strong_count = sum(character in _STRONG_MATH for character in expression)
    variable_count = len(_VARIABLE_TOKEN.findall(expression))
    latex_count = len(_LATEX_COMMAND.findall(expression))
    greek_count = len(_GREEK_RANGE.findall(expression))
    word_count = len(expression.split())
    if word_count > 24:
        return None
    if (
        word_count > 6
        and label is None
        and not any(character in _STRONG_MATH for character in expression)
        and _LATEX_COMMAND.search(expression) is None
    ):
        return None
    supported = (
        (relation_count > 0 and (variable_count > 0 or latex_count > 0))
        or strong_count > 0
        or latex_count > 0
        or (operator_count > 0 and variable_count >= 2)
    )
    if not supported:
        return None
    box = _block_box(item.block.source_spans)
    width_ratio = (
        (box[2] - box[0]) / item.page_width if box is not None else 1.0
    )
    centered = False
    if box is not None:
        center = (box[0] + box[2]) / 2.0
        centered = abs(center - item.page_width / 2.0) <= item.page_width * 0.2
    confidence = 0.55
    if relation_count:
        confidence += 0.12
    if strong_count or latex_count or greek_count:
        confidence += 0.12
    if label is not None:
        confidence += 0.12
    if centered and width_ratio <= 0.85:
        confidence += 0.08
    confidence = min(0.99, confidence)
    evidence: Metadata = (
        ("relation_count", str(relation_count)),
        ("operator_count", str(operator_count)),
        ("strong_math_count", str(strong_count)),
        ("variable_count", str(variable_count)),
        ("latex_command_count", str(latex_count)),
        ("greek_character_count", str(greek_count)),
        ("centered_geometry", str(centered).lower()),
        ("width_ratio", str(width_ratio)),
        ("reading_order", str(item.reading_order)),
        ("layout_confidence", str(item.layout_confidence)),
    )
    return confidence, evidence, label


def _inline_evidence(
    text: str,
    configuration: EquationDetectionConfiguration,
) -> tuple[tuple[int, int, str, float], ...]:
    values: list[tuple[int, int, str, float]] = []
    occupied: list[tuple[int, int]] = []
    for match in _DELIMITED_INLINE.finditer(text):
        if match.group("dollar") is not None:
            start, end = match.span("dollar_body")
            method = "dollar_delimited"
        else:
            start, end = match.span("paren_body")
            method = "latex_parenthesis_delimited"
        body = text[start:end]
        if not _has_math_signal(body):
            continue
        values.append((start, end, method, 0.9))
        occupied.append((start, end))
    for match in _RELATIONAL_INLINE.finditer(text):
        start, end = match.span("body")
        if any(
            start < occupied_end and end > occupied_start
            for occupied_start, occupied_end in occupied
        ):
            continue
        body = text[start:end].rstrip()
        end = start + len(body)
        if not body or len(body) > configuration.max_candidate_text_characters:
            continue
        values.append((start, end, "relational_inline", 0.68))
    values.sort(key=lambda item: (item[0], item[1], item[2]))
    return tuple(values)


def _has_math_signal(value: str) -> bool:
    return bool(
        any(
            character in _RELATIONS or character in _OPERATORS
            for character in value
        )
        or _LATEX_COMMAND.search(value)
        or _GREEK_RANGE.search(value)
    )


def _provisional_display(
    detection_input: EquationDetectionInput,
    ordered: tuple[_OrderedBlock, ...],
    index: int,
    item: _OrderedBlock,
    display: tuple[float, Metadata, str | None],
    box: BoundingBox,
) -> _ProvisionalCandidate:
    confidence, evidence, label = display
    status, warning_code = _status_for_confidence(
        confidence, detection_input.configuration
    )
    return _ProvisionalCandidate(
        key=f"display:{item.block.block_id}",
        kind=EquationCandidateKind.DISPLAY,
        block=item.block,
        source_spans=item.block.source_spans,
        raw_text=item.block.text or "",
        source_label=label,
        selection=_selection_for_box(
            detection_input.document.source,
            item,
            box,
            detection_input.configuration.render_padding_points,
        ),
        preceding_context=_context(ordered, index - 1, item, True),
        following_context=_context(ordered, index + 1, item, False),
        confidence=confidence,
        evidence_status=status,
        evidence=(("detection_method", "display_math_signals"),) + evidence,
        warning_code=warning_code,
    )


def _provisional_inline(
    detection_input: EquationDetectionInput,
    ordered: tuple[_OrderedBlock, ...],
    index: int,
    item: _OrderedBlock,
    inline_index: int,
    start: int,
    end: int,
    method: str,
    confidence: float,
    box: BoundingBox,
) -> _ProvisionalCandidate:
    original_span = item.block.source_spans[0]
    base_offset = original_span.start_offset or 0
    if (
        original_span.end_offset is not None
        and base_offset + end > original_span.end_offset
    ):
        raise ValueError(
            "inline source text exceeds its declared source-span offsets"
        )
    span = SourceSpan(
        source_id=original_span.source_id,
        source_blob_id=original_span.source_blob_id,
        page_index=original_span.page_index,
        printed_page_label=original_span.printed_page_label,
        source_object_id=original_span.source_object_id,
        bounding_box=original_span.bounding_box,
        start_offset=base_offset + start,
        end_offset=base_offset + end,
    )
    status, warning_code = _status_for_confidence(
        confidence, detection_input.configuration
    )
    return _ProvisionalCandidate(
        key=f"inline:{item.block.block_id}:{inline_index}:{start}:{end}",
        kind=EquationCandidateKind.INLINE,
        block=item.block,
        source_spans=(span,),
        raw_text=(item.block.text or "")[start:end],
        source_label=None,
        selection=_selection_for_box(
            detection_input.document.source,
            item,
            box,
            detection_input.configuration.render_padding_points,
        ),
        preceding_context=_context(ordered, index - 1, item, True),
        following_context=_context(ordered, index + 1, item, False),
        confidence=confidence,
        evidence_status=status,
        evidence=(
            ("detection_method", method),
            ("start_offset", str(start)),
            ("end_offset", str(end)),
            ("reading_order", str(item.reading_order)),
            ("layout_confidence", str(item.layout_confidence)),
            ("render_scope", "containing_text_block"),
        ),
        warning_code=warning_code,
    )


def _status_for_confidence(
    confidence: float,
    configuration: EquationDetectionConfiguration,
) -> tuple[EquationEvidenceStatus, str | None]:
    if confidence < configuration.ambiguous_confidence_threshold:
        return EquationEvidenceStatus.AMBIGUOUS, "equation.ambiguous_candidate"
    return EquationEvidenceStatus.PROPOSED, None


def _candidate_warning_spec(
    candidate: _ProvisionalCandidate,
) -> _WarningSpec:
    warning_code = candidate.warning_code
    if warning_code is None:
        raise ValueError("candidate has no warning code")
    return _WarningSpec(
        code=warning_code,
        message="Equation-shaped evidence is an ambiguous candidate",
        object_ids=(),
        candidate_keys=(candidate.key,),
        source_spans=candidate.source_spans,
        evidence=(("confidence", str(candidate.confidence)),),
    )


def _context(
    ordered: tuple[_OrderedBlock, ...],
    index: int,
    candidate: _OrderedBlock,
    preceding: bool,
) -> EquationContextReference | None:
    if index < 0 or index >= len(ordered):
        return None
    other = ordered[index]
    if (
        other.block.source_spans[0].page_index
        != candidate.block.source_spans[0].page_index
    ):
        return None
    return EquationContextReference.create(
        direction=(
            EquationContextDirection.PRECEDING
            if preceding
            else EquationContextDirection.FOLLOWING
        ),
        block=other.block,
    )


def _selection_for_box(
    source: SourceDocument,
    item: _OrderedBlock,
    box: BoundingBox,
    padding: float,
) -> PageRegionSelection:
    padded = (
        max(0.0, box[0] - padding),
        max(0.0, box[1] - padding),
        min(item.page_width, box[2] + padding),
        min(item.page_height, box[3] + padding),
    )
    return PageRegionSelection.for_bounding_box(
        source,
        item.block.source_spans[0].page_index,
        padded,
    )


def _materialize_warnings(
    specs: list[_WarningSpec],
    candidate_by_key: dict[str, EquationCandidate],
) -> tuple[IngestionWarning, ...]:
    warnings: list[IngestionWarning] = []
    for spec in specs:
        if any(key not in candidate_by_key for key in spec.candidate_keys):
            raise ValueError("equation warning candidate is unresolved")
        object_ids = spec.object_ids + tuple(
            candidate_by_key[key].candidate_id for key in spec.candidate_keys
        )
        if len(set(object_ids)) != len(object_ids):
            raise ValueError("equation warning object IDs are duplicated")
        warnings.append(
            IngestionWarning.create(
                code=spec.code,
                severity=WarningSeverity.WARNING,
                message=spec.message,
                object_ids=object_ids,
                source_spans=spec.source_spans,
                evidence=spec.evidence,
            )
        )
    return tuple(warnings)


def _validate_candidate_parts(
    *,
    detection_input_id: str,
    kind: EquationCandidateKind,
    source_block_id: str,
    source_spans: tuple[SourceSpan, ...],
    raw_text: str,
    source_label: str | None,
    rendered_region: RenderedRegion,
    preceding_context: EquationContextReference | None,
    following_context: EquationContextReference | None,
    confidence: float,
    evidence_status: EquationEvidenceStatus,
    evidence: Metadata,
    warning_ids: tuple[str, ...],
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> None:
    _bounded_string("detection input ID", detection_input_id)
    if not isinstance(kind, EquationCandidateKind):
        raise TypeError("kind must be EquationCandidateKind")
    _bounded_string("source block ID", source_block_id)
    _validate_spans(source_spans)
    _bounded_text("raw equation text", raw_text, nonempty=True)
    if len(raw_text) > _MAX_CANDIDATE_TEXT_CHARACTERS:
        raise EquationDetectionLimitError(
            "raw equation text exceeds the implementation maximum"
        )
    if source_label is not None:
        _bounded_text("source equation label", source_label, nonempty=True)
    if not isinstance(rendered_region, RenderedRegion):
        raise TypeError("rendered_region must be RenderedRegion")
    for context in (preceding_context, following_context):
        if context is not None and not isinstance(
            context, EquationContextReference
        ):
            raise TypeError("equation context has an unsupported type")
    _unit_float("confidence", confidence)
    if not isinstance(evidence_status, EquationEvidenceStatus):
        raise TypeError("evidence_status must be EquationEvidenceStatus")
    _validate_metadata(evidence)
    _unique_strings("candidate warning IDs", warning_ids)
    for name, value in (
        ("processor_name", processor_name),
        ("processor_version", processor_version),
        ("configuration_digest", configuration_digest),
    ):
        _bounded_string(name, value)


def _preflight_result(
    detection_input: EquationDetectionInput,
    candidates: tuple[EquationCandidate, ...],
    warnings: tuple[IngestionWarning, ...],
) -> None:
    if not isinstance(candidates, tuple) or not isinstance(warnings, tuple):
        raise TypeError("equation result collections must be immutable tuples")
    config = detection_input.configuration
    if len(candidates) > config.max_candidates:
        raise EquationDetectionLimitError("candidates exceed max_candidates")
    if len(warnings) > config.max_warnings:
        raise EquationDetectionLimitError("warnings exceed max_warnings")
    if any(not isinstance(item, EquationCandidate) for item in candidates):
        raise TypeError("candidates contain an unsupported value")
    if any(not isinstance(item, IngestionWarning) for item in warnings):
        raise TypeError("warnings contain an unsupported value")
    for warning in warnings:
        _validate_warning(warning)


def _validate_rendered_aggregate(
    regions: tuple[RenderedRegion, ...],
    configuration: EquationDetectionConfiguration,
) -> None:
    if any(not isinstance(region, RenderedRegion) for region in regions):
        raise TypeError("renderer returned an unsupported region value")
    unique = {region.region_id: region for region in regions}
    if sum(region.byte_length for region in unique.values()) > (
        configuration.max_total_rendered_png_bytes
    ):
        raise EquationDetectionLimitError(
            "rendered PNG bytes exceed max_total_rendered_png_bytes"
        )
    if (
        sum(
            region.width_pixels * region.height_pixels
            for region in unique.values()
        )
        > configuration.max_total_rendered_pixels
    ):
        raise EquationDetectionLimitError(
            "rendered pixels exceed max_total_rendered_pixels"
        )


def _validate_result(result: EquationDetectionResult) -> None:
    config = result.detection_input.configuration
    _validate_rendered_aggregate(
        tuple(candidate.rendered_region for candidate in result.candidates),
        config,
    )
    for name, value in (
        ("processor_name", result.processor_name),
        ("processor_version", result.processor_version),
        ("configuration_digest", result.configuration_digest),
    ):
        _bounded_string(name, value)
    if result.configuration_digest != config.configuration_digest:
        raise ValueError("equation result configuration digest is stale")
    candidate_ids = tuple(item.candidate_id for item in result.candidates)
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("equation candidate IDs must be unique")
    warning_ids = tuple(item.warning_id for item in result.warnings)
    if len(set(warning_ids)) != len(warning_ids):
        raise ValueError("equation warning IDs must be unique")
    warning_id_set = set(warning_ids)
    document = result.detection_input.document
    block_by_id = {
        block.block_id: block
        for page in document.pages
        for block in page.blocks
    }
    ordered_blocks = _ordered_blocks(result.detection_input)
    ordered_index = {
        item.block.block_id: index for index, item in enumerate(ordered_blocks)
    }
    layout_ids = {layout.result_id for layout in result.detection_input.layouts}
    allowed_warning_objects = set(candidate_ids) | set(block_by_id) | layout_ids
    for warning in result.warnings:
        _validate_warning(warning)
        if not set(warning.object_ids).issubset(allowed_warning_objects):
            raise ValueError("equation warning has unresolved object IDs")
        if any(
            span.source_id != document.source.source_id
            or span.source_blob_id != document.source.blob_id
            for span in warning.source_spans
        ):
            raise ValueError("equation warning spans have the wrong source")
    candidate_order_keys: list[tuple[int, int, int, str]] = []
    inline_counts: dict[str, int] = {}
    for candidate in result.candidates:
        if candidate.detection_input_id != result.detection_input.input_id:
            raise ValueError("candidate detection input link is stale")
        if (
            candidate.processor_name != result.processor_name
            or candidate.processor_version != result.processor_version
        ):
            raise ValueError("candidate processor identity is inconsistent")
        if candidate.configuration_digest != result.configuration_digest:
            raise ValueError("candidate configuration identity is inconsistent")
        if candidate.source_block_id not in block_by_id:
            raise ValueError("candidate source block is unresolved")
        block = block_by_id[candidate.source_block_id]
        if not isinstance(block.text, str):
            raise ValueError("candidate source block has no text")
        _validate_candidate_against_block(candidate, block)
        if len(candidate.raw_text) > config.max_candidate_text_characters:
            raise EquationDetectionLimitError(
                "candidate text exceeds max_candidate_text_characters"
            )
        if candidate.kind is EquationCandidateKind.INLINE:
            inline_counts[candidate.source_block_id] = (
                inline_counts.get(candidate.source_block_id, 0) + 1
            )
            if (
                inline_counts[candidate.source_block_id]
                > config.max_inline_candidates_per_block
            ):
                raise EquationDetectionLimitError(
                    "inline candidates exceed their per-block limit"
                )
        expected_status, _ = _status_for_confidence(
            candidate.confidence, config
        )
        if candidate.evidence_status is not expected_status:
            raise ValueError("candidate evidence status is inconsistent")
        if not set(candidate.warning_ids).issubset(warning_id_set):
            raise ValueError("candidate warning link is unresolved")
        if candidate.evidence_status is EquationEvidenceStatus.AMBIGUOUS:
            if not any(
                warning.code == "equation.ambiguous_candidate"
                and warning.warning_id in candidate.warning_ids
                and candidate.candidate_id in warning.object_ids
                for warning in result.warnings
            ):
                raise ValueError(
                    "ambiguous candidate lacks its specific warning"
                )
        _validate_region(candidate, document)
        candidate_index = ordered_index[candidate.source_block_id]
        span = candidate.source_spans[0]
        candidate_order_keys.append(
            (
                candidate_index,
                span.start_offset if span.start_offset is not None else -1,
                span.end_offset if span.end_offset is not None else -1,
                candidate.candidate_id,
            )
        )
        ordered_item = ordered_blocks[candidate_index]
        _validate_detection_evidence(candidate, ordered_item, config)
        expected_preceding = _context(
            ordered_blocks, candidate_index - 1, ordered_item, True
        )
        expected_following = _context(
            ordered_blocks, candidate_index + 1, ordered_item, False
        )
        if candidate.preceding_context != expected_preceding:
            raise ValueError("candidate preceding context is inconsistent")
        if candidate.following_context != expected_following:
            raise ValueError("candidate following context is inconsistent")
        _validate_context(candidate.preceding_context, block_by_id)
        _validate_context(candidate.following_context, block_by_id)
    if candidate_order_keys != sorted(candidate_order_keys):
        raise ValueError("equation candidates are not in source reading order")
    _validate_retained_size(result, config.max_result_bytes)


def _validate_detection_evidence(
    candidate: EquationCandidate,
    item: _OrderedBlock,
    configuration: EquationDetectionConfiguration,
) -> None:
    block_text = item.block.text
    if block_text is None:
        raise ValueError("candidate text block has no text")
    if candidate.kind is EquationCandidateKind.DISPLAY:
        display = _display_evidence(block_text, item, configuration)
        if display is None:
            raise ValueError("display candidate lacks detection evidence")
        confidence, evidence, label = display
        expected_evidence = (
            ("detection_method", "display_math_signals"),
        ) + evidence
        if (
            candidate.confidence != confidence
            or candidate.source_label != label
            or candidate.evidence != expected_evidence
        ):
            raise ValueError("display candidate evidence is inconsistent")
        return
    span = candidate.source_spans[0]
    original = item.block.source_spans[0]
    if span.start_offset is None or span.end_offset is None:
        raise ValueError("inline candidate source offsets are missing")
    start = span.start_offset - (original.start_offset or 0)
    end = span.end_offset - (original.start_offset or 0)
    inline = _inline_evidence(block_text, configuration)
    matches = tuple(
        value for value in inline if value[0] == start and value[1] == end
    )
    if len(matches) != 1:
        raise ValueError("inline candidate lacks unique detection evidence")
    _, _, method, confidence = matches[0]
    inline_expected_evidence: Metadata = (
        ("detection_method", method),
        ("start_offset", str(start)),
        ("end_offset", str(end)),
        ("reading_order", str(item.reading_order)),
        ("layout_confidence", str(item.layout_confidence)),
        ("render_scope", "containing_text_block"),
    )
    if (
        candidate.confidence != confidence
        or candidate.evidence != inline_expected_evidence
    ):
        raise ValueError("inline candidate evidence is inconsistent")


def _validate_candidate_against_block(
    candidate: EquationCandidate,
    block: ExtractedBlock,
) -> None:
    block_text = block.text
    if block_text is None:
        raise ValueError("candidate source block has no text")
    if candidate.kind is EquationCandidateKind.DISPLAY:
        if (
            candidate.raw_text != block_text
            or candidate.source_spans != block.source_spans
        ):
            raise ValueError(
                "display candidate does not preserve block evidence"
            )
        expected_label_match = _TRAILING_LABEL.search(block_text.strip())
        expected_label = (
            expected_label_match.group("label")
            if expected_label_match is not None
            else None
        )
        if candidate.source_label != expected_label:
            raise ValueError("display equation label is inconsistent")
    else:
        if len(candidate.source_spans) != 1 or len(block.source_spans) != 1:
            raise ValueError("inline candidate source span is ambiguous")
        span = candidate.source_spans[0]
        original = block.source_spans[0]
        base = original.start_offset or 0
        if span.start_offset is None or span.end_offset is None:
            raise ValueError("inline candidate requires source offsets")
        start = span.start_offset - base
        end = span.end_offset - base
        if start < 0 or end > len(block_text) or start >= end:
            raise ValueError("inline candidate offsets are outside source text")
        if (
            original.end_offset is not None
            and span.end_offset > original.end_offset
        ):
            raise ValueError(
                "inline candidate exceeds declared source-span offsets"
            )
        if candidate.raw_text != block_text[start:end]:
            raise ValueError("inline candidate text does not match its offsets")
        expected_span = SourceSpan(
            source_id=original.source_id,
            source_blob_id=original.source_blob_id,
            page_index=original.page_index,
            printed_page_label=original.printed_page_label,
            source_object_id=original.source_object_id,
            bounding_box=original.bounding_box,
            start_offset=span.start_offset,
            end_offset=span.end_offset,
        )
        if span != expected_span or candidate.source_label is not None:
            raise ValueError("inline candidate source evidence is inconsistent")


def _validate_region(
    candidate: EquationCandidate,
    document: ExtractedDocument,
) -> None:
    region = candidate.rendered_region
    source = document.source
    page_by_index = {page.page_index: page for page in document.pages}
    page = page_by_index[candidate.source_spans[0].page_index]
    if (
        region.source_id != source.source_id
        or region.source_blob_id != source.blob_id
        or region.source_content_hash != source.content_hash
        or region.page_index != candidate.source_spans[0].page_index
        or region.selection_was_full_page
        or region.coordinate_system != PYMUPDF_COORDINATE_SYSTEM
        or region.page_rotation_degrees != page.rotation_degrees
    ):
        raise ValueError(
            "candidate rendered region has inconsistent provenance"
        )
    box = _block_box(candidate.source_spans)
    if box is None:
        raise ValueError("candidate source spans have no complete geometry")
    selected = region.source_bounding_box
    if not (
        selected[0] <= box[0]
        and selected[1] <= box[1]
        and selected[2] >= box[2]
        and selected[3] >= box[3]
    ):
        raise ValueError("candidate rendered region does not contain evidence")


def _validate_context(
    context: EquationContextReference | None,
    block_by_id: dict[str, ExtractedBlock],
) -> None:
    if context is None:
        return
    block = block_by_id.get(context.block_id)
    if block is None or block.source_spans != context.source_spans:
        raise ValueError("equation context reference is stale")


def _validate_warning(warning: IngestionWarning) -> None:
    _bounded_string("warning ID", warning.warning_id)
    _bounded_string("warning code", warning.code)
    if not isinstance(warning.severity, WarningSeverity):
        raise TypeError("warning severity must be WarningSeverity")
    _bounded_text("warning message", warning.message, nonempty=True)
    _unique_strings("warning object IDs", warning.object_ids)
    _validate_spans(warning.source_spans, required=False)
    _validate_metadata(warning.evidence)
    if warning.suggested_recovery is not None:
        _bounded_text("warning suggested recovery", warning.suggested_recovery)
    expected = stable_id(
        "warning",
        warning.code,
        warning.object_ids,
        tuple(span.identity_parts() for span in warning.source_spans),
        warning.evidence,
    )
    if warning.warning_id != expected:
        raise ValueError("equation warning ID is inconsistent")


def _candidate_id(
    *,
    detection_input_id: str,
    kind: EquationCandidateKind,
    source_block_id: str,
    source_spans: tuple[SourceSpan, ...],
    raw_text: str,
    source_label: str | None,
    rendered_region_id: str,
    preceding_context_id: str | None,
    following_context_id: str | None,
    confidence: float,
    evidence_status: EquationEvidenceStatus,
    evidence: Metadata,
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "equation-candidate",
        EQUATION_CONTRACT_VERSION,
        detection_input_id,
        kind.value,
        source_block_id,
        tuple(span.identity_parts() for span in source_spans),
        raw_text,
        source_label,
        rendered_region_id,
        preceding_context_id,
        following_context_id,
        confidence,
        evidence_status.value,
        evidence,
        processor_name,
        processor_version,
        configuration_digest,
    )


def _context_id(
    direction: EquationContextDirection,
    block_id: str,
    source_spans: tuple[SourceSpan, ...],
) -> str:
    return stable_id(
        "equation-context",
        direction.value,
        block_id,
        tuple(span.identity_parts() for span in source_spans),
    )


def _result_id(
    input_id: str,
    candidates: tuple[EquationCandidate, ...],
    warnings: tuple[IngestionWarning, ...],
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "equation-detection-result",
        EQUATION_CONTRACT_VERSION,
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


def _block_box(source_spans: tuple[SourceSpan, ...]) -> BoundingBox | None:
    boxes = tuple(
        span.bounding_box
        for span in source_spans
        if span.bounding_box is not None
    )
    if len(boxes) != len(source_spans) or not boxes:
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


def _validate_spans(
    spans: tuple[SourceSpan, ...], *, required: bool = True
) -> None:
    if not isinstance(spans, tuple):
        raise TypeError("source spans must be an immutable tuple")
    if required and not spans:
        raise ValueError("source spans must be non-empty")
    if len(spans) > _MAX_SOURCE_SPANS:
        raise EquationDetectionLimitError("source spans exceed their limit")
    if any(not isinstance(span, SourceSpan) for span in spans):
        raise TypeError("source spans must contain SourceSpan values")


def _validate_metadata(value: Metadata) -> None:
    if not isinstance(value, tuple):
        raise TypeError("metadata must be an immutable tuple")
    if len(value) > 128:
        raise EquationDetectionLimitError("metadata entries exceed their limit")
    total_characters = 0
    for entry in value:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("metadata must contain immutable key/value pairs")
        key, item = entry
        _bounded_string("metadata key", key)
        _bounded_text("metadata value", item)
        total_characters += len(key) + len(item)
        if total_characters > _MAX_METADATA_CHARACTERS:
            raise EquationDetectionLimitError(
                "metadata exceeds its aggregate character limit"
            )


def _unique_strings(name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be an immutable tuple")
    if len(values) > _MAX_INPUT_BLOCKS:
        raise EquationDetectionLimitError(f"{name} exceeds its limit")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must contain unique values")
    for value in values:
        _bounded_string(name, value)


def _bounded_string(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or len(value) > _MAX_IDENTITY_CHARACTERS:
        raise ValueError(
            f"{name} must contain 1 to {_MAX_IDENTITY_CHARACTERS} characters"
        )
    _valid_unicode(name, value)


def _bounded_text(
    name: str,
    value: object,
    *,
    nonempty: bool = False,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if nonempty and not value:
        raise ValueError(f"{name} must be non-empty")
    if len(value) > _MAX_TEXT_CHARACTERS:
        raise EquationDetectionLimitError(f"{name} exceeds its limit")
    _valid_unicode(name, value)


def _valid_unicode(name: str, value: str) -> None:
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a finite number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be a finite number")
    return 0.0 if normalized == 0.0 else normalized


def _unit_float(name: str, value: object) -> float:
    normalized = _finite_float(name, value)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{name} must be between zero and one")
    return normalized


def _validated_box(value: BoundingBox) -> BoundingBox:
    if not isinstance(value, tuple) or len(value) != 4:
        raise TypeError("bounding box must be an immutable four-tuple")
    coordinates = tuple(
        _finite_float("bounding box coordinate", item) for item in value
    )
    x0, y0, x1, y1 = coordinates
    if x0 < 0.0 or y0 < 0.0 or x1 <= x0 or y1 <= y0:
        raise ValueError("bounding box must have non-negative positive area")
    return (
        coordinates[0],
        coordinates[1],
        coordinates[2],
        coordinates[3],
    )


def _validate_retained_size(value: object, limit: int) -> None:
    total = 0
    stack: list[object] = [value]
    while stack:
        item = stack.pop()
        if item is None:
            increment = 4
        elif isinstance(item, str):
            increment = len(item.encode("utf-8")) + 2
        elif isinstance(item, bytes):
            increment = len(item)
        elif isinstance(item, Enum):
            stack.append(item.value)
            increment = 0
        elif isinstance(item, bool | int | float):
            increment = 32
        elif isinstance(item, tuple):
            increment = 2 + len(item)
            stack.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            increment = 2
            for field_value in fields(item):
                increment += len(field_value.name) + 3
                if (
                    isinstance(item, RenderedRegion)
                    and field_value.name == "content"
                ):
                    continue
                stack.append(getattr(item, field_value.name))
        else:
            raise TypeError("equation result contains unsupported evidence")
        total += increment
        if total > limit:
            raise EquationDetectionLimitError(
                "equation result exceeds max_result_bytes"
            )

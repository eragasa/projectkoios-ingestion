from __future__ import annotations

import math
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass, fields, is_dataclass
from difflib import SequenceMatcher
from enum import Enum, StrEnum

from projectkoios.ingestion.base import BaseOcrReconciler
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedBlock,
    ExtractedPage,
    Metadata,
    SourceSpan,
    WarningSeverity,
)
from projectkoios.ingestion.ocr.models import (
    OCRLine,
    OcrResult,
    OCRSelection,
    OCRSelectionResult,
    OCRSelectionStatus,
)
from projectkoios.ingestion.pdf.models import RenderedRegion

OCR_RECONCILIATION_CONTRACT_VERSION = "1.0"
_MAX_NATIVE_BLOCKS = 1_024
_MAX_NATIVE_SEGMENTS = 4_096
_MAX_OCR_LINES = 25_000
_MAX_CANDIDATE_PAIRS = 250_000
_MAX_COMPARISON_WORK = 25_000_000
_MAX_COMPARISON_TEXT_CHARACTERS = 100_000
_MAX_TEXT_CHARACTERS_PER_ITEM = 1_000_000
_MAX_TOTAL_TEXT_CHARACTERS = 5_000_000
_MAX_WARNINGS = 8_192
_MAX_WARNING_EVIDENCE_ENTRIES = 64
_MAX_WARNING_EVIDENCE_CHARACTERS = 100_000
_MAX_SOURCE_SPANS_PER_BLOCK = 2_048
_MAX_LINKED_IDS = _MAX_NATIVE_SEGMENTS + _MAX_OCR_LINES
_MAX_IDENTITY_CHARACTERS = 4_096
_MAX_RESULT_BYTES = 64_000_000
_LINE_BOUNDARIES = frozenset(
    ("\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029")
)


class OCRReconciliationLimitError(ValueError):
    """Raised before reconciliation work exceeds a configured hard bound."""


class OCRReconciliationMatchKind(StrEnum):
    DUPLICATE = "duplicate"
    DISAGREEMENT = "disagreement"


class OCRReconciledItemKind(StrEnum):
    DUPLICATE = "duplicate"
    DISAGREEMENT = "disagreement"
    NATIVE_ONLY = "native_only"
    OCR_ONLY = "ocr_only"


class OCRReconciliationStreamChoice(StrEnum):
    NATIVE = "native"
    OCR = "ocr"
    PROPOSED_MERGED = "proposed_merged"


@dataclass(frozen=True)
class OCRReconciliationConfiguration:
    """Deterministic matching thresholds and hard processing limits."""

    minimum_geometry_overlap: float = 0.5
    minimum_disagreement_similarity: float = 0.5
    ambiguity_score_delta: float = 0.02
    max_native_blocks: int = _MAX_NATIVE_BLOCKS
    max_native_segments: int = _MAX_NATIVE_SEGMENTS
    max_ocr_lines: int = _MAX_OCR_LINES
    max_candidate_pairs: int = _MAX_CANDIDATE_PAIRS
    max_comparison_work: int = _MAX_COMPARISON_WORK
    max_comparison_text_characters: int = _MAX_COMPARISON_TEXT_CHARACTERS
    max_text_characters_per_item: int = _MAX_TEXT_CHARACTERS_PER_ITEM
    max_total_text_characters: int = _MAX_TOTAL_TEXT_CHARACTERS
    max_warnings: int = _MAX_WARNINGS
    max_result_bytes: int = _MAX_RESULT_BYTES

    def __post_init__(self) -> None:
        for name in (
            "minimum_geometry_overlap",
            "minimum_disagreement_similarity",
            "ambiguity_score_delta",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError(f"{name} must be a finite number")
            normalized = float(value)
            requires_positive = name != "ambiguity_score_delta"
            if (
                not math.isfinite(normalized)
                or normalized > 1.0
                or normalized < 0.0
                or (requires_positive and normalized == 0.0)
            ):
                qualifier = "greater than zero and" if requires_positive else ""
                raise ValueError(
                    f"{name} must be {qualifier} no greater than one"
                )
            object.__setattr__(self, name, normalized)
        for name, hard_maximum in (
            ("max_native_blocks", _MAX_NATIVE_BLOCKS),
            ("max_native_segments", _MAX_NATIVE_SEGMENTS),
            ("max_ocr_lines", _MAX_OCR_LINES),
            ("max_candidate_pairs", _MAX_CANDIDATE_PAIRS),
            ("max_comparison_work", _MAX_COMPARISON_WORK),
            (
                "max_comparison_text_characters",
                _MAX_COMPARISON_TEXT_CHARACTERS,
            ),
            (
                "max_text_characters_per_item",
                _MAX_TEXT_CHARACTERS_PER_ITEM,
            ),
            ("max_total_text_characters", _MAX_TOTAL_TEXT_CHARACTERS),
            ("max_warnings", _MAX_WARNINGS),
            ("max_result_bytes", _MAX_RESULT_BYTES),
        ):
            value = getattr(self, name)
            _positive_integer(name, value)
            if value > hard_maximum:
                raise OCRReconciliationLimitError(
                    f"{name} exceeds the implementation maximum "
                    f"({hard_maximum})"
                )

    @property
    def configuration_digest(self) -> str:
        return stable_id(
            "ocr-reconciliation-configuration", self.identity_parts()
        )

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.minimum_geometry_overlap,
            self.minimum_disagreement_similarity,
            self.ambiguity_score_delta,
            self.max_native_blocks,
            self.max_native_segments,
            self.max_ocr_lines,
            self.max_candidate_pairs,
            self.max_comparison_work,
            self.max_comparison_text_characters,
            self.max_text_characters_per_item,
            self.max_total_text_characters,
            self.max_warnings,
            self.max_result_bytes,
        )


@dataclass(frozen=True)
class OCRNativeBlockEvidence:
    """One exact selected native text block in layout-proposed order."""

    evidence_id: str
    block_id: str
    text: str
    source_spans: tuple[SourceSpan, ...]
    order: int

    @classmethod
    def from_block(
        cls, block: ExtractedBlock, *, order: int
    ) -> OCRNativeBlockEvidence:
        if block.kind != "text" or not isinstance(block.text, str):
            raise ValueError("native reconciliation evidence must contain text")
        _bounded_string("native block ID", block.block_id)
        _bounded_text("native block text", block.text)
        _require_tuple("native source spans", block.source_spans)
        if len(block.source_spans) > _MAX_SOURCE_SPANS_PER_BLOCK:
            raise OCRReconciliationLimitError(
                "native source spans exceed the implementation maximum"
            )
        _nonnegative_integer("native block order", order)
        evidence_id = _native_block_evidence_id(block, order)
        return cls(
            evidence_id=evidence_id,
            block_id=block.block_id,
            text=block.text,
            source_spans=block.source_spans,
            order=order,
        )

    def __post_init__(self) -> None:
        _bounded_string("native evidence ID", self.evidence_id)
        _bounded_string("native block ID", self.block_id)
        _bounded_text("native block text", self.text)
        _require_tuple("native source spans", self.source_spans)
        if not self.source_spans:
            raise ValueError("native block evidence requires source spans")
        if len(self.source_spans) > _MAX_SOURCE_SPANS_PER_BLOCK:
            raise OCRReconciliationLimitError(
                "native source spans exceed the implementation maximum"
            )
        if any(not isinstance(span, SourceSpan) for span in self.source_spans):
            raise TypeError(
                "native source spans must contain SourceSpan values"
            )
        _nonnegative_integer("native block order", self.order)
        expected = stable_id(
            "ocr-native-block-evidence",
            OCR_RECONCILIATION_CONTRACT_VERSION,
            self.block_id,
            self.text,
            tuple(span.identity_parts() for span in self.source_spans),
            self.order,
        )
        if self.evidence_id != expected:
            raise ValueError("native block evidence ID is inconsistent")

    @property
    def bounding_box(self) -> BoundingBox | None:
        return _spans_bounding_box(self.source_spans)


@dataclass(frozen=True)
class OCRNativeLineSegment:
    """A source-backed text line projected from one native block payload."""

    segment_id: str
    block_evidence_id: str
    block_id: str
    line_index: int
    text: str
    normalized_text: str
    source_bounding_box: BoundingBox | None
    order: int

    @classmethod
    def create(
        cls,
        *,
        block: OCRNativeBlockEvidence,
        line_index: int,
        text: str,
        order: int,
    ) -> OCRNativeLineSegment:
        if not isinstance(block, OCRNativeBlockEvidence):
            raise TypeError("block must be OCRNativeBlockEvidence")
        _nonnegative_integer("line_index", line_index)
        _nonnegative_integer("segment order", order)
        _bounded_text("native segment text", text, nonempty=True)
        normalized = _normalized_text(text)
        bounding_box = block.bounding_box
        segment_id = _native_segment_id(
            block.evidence_id,
            block.block_id,
            line_index,
            text,
            normalized,
            bounding_box,
            order,
        )
        return cls(
            segment_id=segment_id,
            block_evidence_id=block.evidence_id,
            block_id=block.block_id,
            line_index=line_index,
            text=text,
            normalized_text=normalized,
            source_bounding_box=bounding_box,
            order=order,
        )

    def __post_init__(self) -> None:
        for name, value in (
            ("segment_id", self.segment_id),
            ("block_evidence_id", self.block_evidence_id),
            ("block_id", self.block_id),
        ):
            _bounded_string(name, value)
        _nonnegative_integer("line_index", self.line_index)
        _nonnegative_integer("segment order", self.order)
        _bounded_text("native segment text", self.text, nonempty=True)
        expected_normalized = _normalized_text(self.text)
        if not expected_normalized:
            raise ValueError("native segment text must contain visible text")
        if self.normalized_text != expected_normalized:
            raise ValueError("native segment normalized text is inconsistent")
        if self.source_bounding_box is not None:
            object.__setattr__(
                self,
                "source_bounding_box",
                _validated_box(self.source_bounding_box),
            )
        expected = _native_segment_id(
            self.block_evidence_id,
            self.block_id,
            self.line_index,
            self.text,
            self.normalized_text,
            self.source_bounding_box,
            self.order,
        )
        if self.segment_id != expected:
            raise ValueError("native segment ID is inconsistent")


@dataclass(frozen=True)
class OCRReconciliationWarning:
    warning_id: str
    code: str
    severity: WarningSeverity
    message: str
    object_ids: tuple[str, ...]
    evidence: Metadata = ()

    @classmethod
    def create(
        cls,
        *,
        code: str,
        severity: WarningSeverity,
        message: str,
        object_ids: tuple[str, ...],
        evidence: Metadata = (),
    ) -> OCRReconciliationWarning:
        _bounded_string("warning code", code)
        if not isinstance(severity, WarningSeverity):
            raise ValueError("warning severity is unsupported")
        _bounded_text("warning message", message, nonempty=True)
        _require_unique_strings("warning object IDs", object_ids, True)
        _validate_metadata(evidence)
        warning_id = _warning_id(code, severity, message, object_ids, evidence)
        return cls(
            warning_id=warning_id,
            code=code,
            severity=severity,
            message=message,
            object_ids=object_ids,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        _bounded_string("warning ID", self.warning_id)
        _bounded_string("warning code", self.code)
        if not isinstance(self.severity, WarningSeverity):
            raise ValueError("warning severity is unsupported")
        _bounded_text("warning message", self.message, nonempty=True)
        _require_unique_strings("warning object IDs", self.object_ids, True)
        _validate_metadata(self.evidence)
        expected = _warning_id(
            self.code,
            self.severity,
            self.message,
            self.object_ids,
            self.evidence,
        )
        if self.warning_id != expected:
            raise ValueError("reconciliation warning ID is inconsistent")


@dataclass(frozen=True)
class OCRReconciliationMatch:
    match_id: str
    kind: OCRReconciliationMatchKind
    native_segment_id: str
    ocr_line_id: str
    text_similarity: float
    geometry_overlap: float | None
    warning_ids: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        kind: OCRReconciliationMatchKind,
        native_segment_id: str,
        ocr_line_id: str,
        text_similarity: float,
        geometry_overlap: float | None,
        warning_ids: tuple[str, ...] = (),
    ) -> OCRReconciliationMatch:
        if not isinstance(kind, OCRReconciliationMatchKind):
            raise ValueError("reconciliation match kind is unsupported")
        _bounded_string("native segment ID", native_segment_id)
        _bounded_string("OCR line ID", ocr_line_id)
        _require_unique_strings("match warning IDs", warning_ids)
        similarity = _unit_float("text_similarity", text_similarity)
        overlap = (
            _unit_float("geometry_overlap", geometry_overlap)
            if geometry_overlap is not None
            else None
        )
        match_id = _match_id(
            kind,
            native_segment_id,
            ocr_line_id,
            similarity,
            overlap,
            warning_ids,
        )
        return cls(
            match_id=match_id,
            kind=kind,
            native_segment_id=native_segment_id,
            ocr_line_id=ocr_line_id,
            text_similarity=similarity,
            geometry_overlap=overlap,
            warning_ids=warning_ids,
        )

    def __post_init__(self) -> None:
        _bounded_string("match ID", self.match_id)
        if not isinstance(self.kind, OCRReconciliationMatchKind):
            raise ValueError("reconciliation match kind is unsupported")
        _bounded_string("native segment ID", self.native_segment_id)
        _bounded_string("OCR line ID", self.ocr_line_id)
        object.__setattr__(
            self,
            "text_similarity",
            _unit_float("text_similarity", self.text_similarity),
        )
        if self.geometry_overlap is not None:
            object.__setattr__(
                self,
                "geometry_overlap",
                _unit_float("geometry_overlap", self.geometry_overlap),
            )
        _require_unique_strings("match warning IDs", self.warning_ids)
        if self.kind is OCRReconciliationMatchKind.DUPLICATE:
            if self.text_similarity != 1.0 or self.warning_ids:
                raise ValueError(
                    "duplicate matches require exact text and no warning"
                )
        elif not self.warning_ids:
            raise ValueError("disagreement matches require warning evidence")
        expected = _match_id(
            self.kind,
            self.native_segment_id,
            self.ocr_line_id,
            self.text_similarity,
            self.geometry_overlap,
            self.warning_ids,
        )
        if self.match_id != expected:
            raise ValueError("reconciliation match ID is inconsistent")


@dataclass(frozen=True)
class OCRReconciledItem:
    item_id: str
    kind: OCRReconciledItemKind
    order: int
    native_segment_id: str | None
    ocr_line_id: str | None
    proposed_text: str | None
    warning_ids: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        kind: OCRReconciledItemKind,
        order: int,
        native_segment_id: str | None,
        ocr_line_id: str | None,
        proposed_text: str | None,
        warning_ids: tuple[str, ...] = (),
    ) -> OCRReconciledItem:
        if not isinstance(kind, OCRReconciledItemKind):
            raise ValueError("reconciled item kind is unsupported")
        _nonnegative_integer("reconciled item order", order)
        for name, value in (
            ("native_segment_id", native_segment_id),
            ("ocr_line_id", ocr_line_id),
        ):
            if value is not None:
                _bounded_string(name, value)
        if proposed_text is not None:
            _bounded_text("proposed text", proposed_text, nonempty=True)
        _require_unique_strings("item warning IDs", warning_ids)
        item_id = _item_id(
            kind,
            order,
            native_segment_id,
            ocr_line_id,
            proposed_text,
            warning_ids,
        )
        return cls(
            item_id=item_id,
            kind=kind,
            order=order,
            native_segment_id=native_segment_id,
            ocr_line_id=ocr_line_id,
            proposed_text=proposed_text,
            warning_ids=warning_ids,
        )

    def __post_init__(self) -> None:
        _bounded_string("reconciled item ID", self.item_id)
        if not isinstance(self.kind, OCRReconciledItemKind):
            raise ValueError("reconciled item kind is unsupported")
        _nonnegative_integer("reconciled item order", self.order)
        for name, value in (
            ("native_segment_id", self.native_segment_id),
            ("ocr_line_id", self.ocr_line_id),
        ):
            if value is not None:
                _bounded_string(name, value)
        if self.proposed_text is not None:
            _bounded_text("proposed text", self.proposed_text, nonempty=True)
        _require_unique_strings("item warning IDs", self.warning_ids)
        if self.kind is OCRReconciledItemKind.DUPLICATE:
            if (
                self.native_segment_id is None
                or self.ocr_line_id is None
                or self.proposed_text is None
                or self.warning_ids
            ):
                raise ValueError("duplicate item evidence is incomplete")
        elif self.kind is OCRReconciledItemKind.DISAGREEMENT:
            if (
                self.native_segment_id is None
                or self.ocr_line_id is None
                or self.proposed_text is not None
                or not self.warning_ids
            ):
                raise ValueError("disagreement item evidence is incomplete")
        elif self.kind is OCRReconciledItemKind.NATIVE_ONLY:
            if (
                self.native_segment_id is None
                or self.ocr_line_id is not None
                or self.proposed_text is None
            ):
                raise ValueError("native-only item evidence is inconsistent")
        elif (
            self.native_segment_id is not None
            or self.ocr_line_id is None
            or self.proposed_text is None
        ):
            raise ValueError("OCR-only item evidence is inconsistent")
        expected = _item_id(
            self.kind,
            self.order,
            self.native_segment_id,
            self.ocr_line_id,
            self.proposed_text,
            self.warning_ids,
        )
        if self.item_id != expected:
            raise ValueError("reconciled item ID is inconsistent")


@dataclass(frozen=True)
class OCRReconciliationInput:
    input_id: str
    ocr_result: OcrResult
    selection_index: int
    native_page: ExtractedPage | None
    layout_result: PageLayoutResult | None
    configuration: OCRReconciliationConfiguration
    contract_version: str = OCR_RECONCILIATION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        ocr_result: OcrResult,
        selection_index: int,
        native_page: ExtractedPage | None = None,
        layout_result: PageLayoutResult | None = None,
        configuration: OCRReconciliationConfiguration | None = None,
    ) -> OCRReconciliationInput:
        config = configuration or OCRReconciliationConfiguration()
        _validate_input_parts(
            ocr_result,
            selection_index,
            native_page,
            layout_result,
            config,
        )
        input_id = _input_id(
            ocr_result,
            selection_index,
            native_page,
            layout_result,
            config,
        )
        return cls(
            input_id=input_id,
            ocr_result=ocr_result,
            selection_index=selection_index,
            native_page=native_page,
            layout_result=layout_result,
            configuration=config,
        )

    def __post_init__(self) -> None:
        if self.contract_version != OCR_RECONCILIATION_CONTRACT_VERSION:
            raise ValueError("unsupported OCR reconciliation input version")
        _bounded_string("reconciliation input ID", self.input_id)
        _validate_input_parts(
            self.ocr_result,
            self.selection_index,
            self.native_page,
            self.layout_result,
            self.configuration,
        )
        expected = _input_id(
            self.ocr_result,
            self.selection_index,
            self.native_page,
            self.layout_result,
            self.configuration,
        )
        if self.input_id != expected:
            raise ValueError("OCR reconciliation input ID is inconsistent")

    @property
    def selection(self) -> OCRSelection:
        return self.ocr_result.request.selections[self.selection_index]

    @property
    def selection_result(self) -> OCRSelectionResult:
        return self.ocr_result.selection_results[self.selection_index]


@dataclass(frozen=True)
class OCRReconciliationResult:
    result_id: str
    reconciliation_input: OCRReconciliationInput
    native_stream: tuple[OCRNativeBlockEvidence, ...]
    native_segments: tuple[OCRNativeLineSegment, ...]
    ocr_stream: tuple[OCRLine, ...]
    matches: tuple[OCRReconciliationMatch, ...]
    proposed_merged_stream: tuple[OCRReconciledItem, ...]
    warnings: tuple[OCRReconciliationWarning, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = OCR_RECONCILIATION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        reconciliation_input: OCRReconciliationInput,
        native_stream: tuple[OCRNativeBlockEvidence, ...],
        native_segments: tuple[OCRNativeLineSegment, ...],
        ocr_stream: tuple[OCRLine, ...],
        matches: tuple[OCRReconciliationMatch, ...],
        proposed_merged_stream: tuple[OCRReconciledItem, ...],
        warnings: tuple[OCRReconciliationWarning, ...],
        processor_name: str,
        processor_version: str,
    ) -> OCRReconciliationResult:
        if not isinstance(reconciliation_input, OCRReconciliationInput):
            raise TypeError("reconciliation_input has the wrong type")
        configuration_digest = (
            reconciliation_input.configuration.configuration_digest
        )
        _preflight_result_collections(
            reconciliation_input,
            native_stream,
            native_segments,
            ocr_stream,
            matches,
            proposed_merged_stream,
            warnings,
        )
        result_id = _result_id(
            reconciliation_input.input_id,
            native_stream,
            native_segments,
            ocr_stream,
            matches,
            proposed_merged_stream,
            warnings,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            result_id=result_id,
            reconciliation_input=reconciliation_input,
            native_stream=native_stream,
            native_segments=native_segments,
            ocr_stream=ocr_stream,
            matches=matches,
            proposed_merged_stream=proposed_merged_stream,
            warnings=warnings,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != OCR_RECONCILIATION_CONTRACT_VERSION:
            raise ValueError("unsupported OCR reconciliation result version")
        if not isinstance(self.reconciliation_input, OCRReconciliationInput):
            raise TypeError("reconciliation_input has the wrong type")
        for name in (
            "native_stream",
            "native_segments",
            "ocr_stream",
            "matches",
            "proposed_merged_stream",
            "warnings",
        ):
            _require_tuple(name, getattr(self, name))
        _validate_result(self)
        expected = _result_id(
            self.reconciliation_input.input_id,
            self.native_stream,
            self.native_segments,
            self.ocr_stream,
            self.matches,
            self.proposed_merged_stream,
            self.warnings,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        if self.result_id != expected:
            raise ValueError("OCR reconciliation result ID is inconsistent")

    def stream(
        self, choice: OCRReconciliationStreamChoice
    ) -> (
        tuple[OCRNativeBlockEvidence, ...]
        | tuple[OCRLine, ...]
        | tuple[OCRReconciledItem, ...]
    ):
        if choice is OCRReconciliationStreamChoice.NATIVE:
            return self.native_stream
        if choice is OCRReconciliationStreamChoice.OCR:
            return self.ocr_stream
        if choice is OCRReconciliationStreamChoice.PROPOSED_MERGED:
            return self.proposed_merged_stream
        raise ValueError("unsupported OCR reconciliation stream choice")


@dataclass(frozen=True)
class _Candidate:
    native_segment_id: str
    ocr_line_id: str
    kind: OCRReconciliationMatchKind
    text_similarity: float
    geometry_overlap: float | None
    score: float
    native_order: int
    ocr_order: int


class DeterministicOCRReconciler(BaseOcrReconciler):
    """Conservatively propose a merged stream without replacing evidence."""

    name = "deterministic-ocr-reconciler"
    version = "1"

    def reconcile(
        self, reconciliation_input: OCRReconciliationInput
    ) -> OCRReconciliationResult:
        if not isinstance(reconciliation_input, OCRReconciliationInput):
            raise TypeError(
                "reconciliation_input must be OCRReconciliationInput"
            )
        native_stream = _native_stream(reconciliation_input)
        native_segments = _native_segments(
            native_stream, reconciliation_input.configuration
        )
        ocr_stream = reconciliation_input.selection_result.lines
        config = reconciliation_input.configuration
        if len(ocr_stream) > config.max_ocr_lines:
            raise OCRReconciliationLimitError(
                "OCR line count exceeds max_ocr_lines"
            )
        if reconciliation_input.selection_result.tokens and not ocr_stream:
            raise ValueError(
                "OCR reconciliation requires line evidence, not tokens alone"
            )
        pair_count = len(native_segments) * len(ocr_stream)
        if pair_count > config.max_candidate_pairs:
            raise OCRReconciliationLimitError(
                "candidate pairs exceed max_candidate_pairs"
            )
        warnings = _input_warnings(reconciliation_input)
        candidates, comparison_warnings = _candidates(
            native_segments, ocr_stream, config
        )
        warnings.extend(comparison_warnings)
        selected_candidates, match_warnings = _matches(candidates, config)
        warnings.extend(match_warnings)
        matched_ocr_ids = {
            candidate.ocr_line_id for candidate in selected_candidates
        }
        unmatched_ocr_ids = tuple(
            line.line_id
            for line in ocr_stream
            if line.line_id not in matched_ocr_ids
        )
        if native_segments and unmatched_ocr_ids:
            warnings.append(
                OCRReconciliationWarning.create(
                    code="ocr.reconciliation.ocr_only_order_uncertain",
                    severity=WarningSeverity.WARNING,
                    message=(
                        "Unmatched OCR evidence is appended after the "
                        "layout-ordered native stream"
                    ),
                    object_ids=unmatched_ocr_ids,
                    evidence=(("ordering_policy", "append_after_native"),),
                )
            )
        if len(warnings) > config.max_warnings:
            raise OCRReconciliationLimitError(
                "warning count exceeds max_warnings"
            )
        warning_by_id = {warning.warning_id: warning for warning in warnings}
        matches = tuple(
            _match_with_warning(candidate, warning_by_id)
            for candidate in selected_candidates
        )
        proposed = _merged_stream(
            native_segments,
            ocr_stream,
            matches,
            tuple(warnings),
        )
        return OCRReconciliationResult.create(
            reconciliation_input=reconciliation_input,
            native_stream=native_stream,
            native_segments=native_segments,
            ocr_stream=ocr_stream,
            matches=matches,
            proposed_merged_stream=proposed,
            warnings=tuple(warnings),
            processor_name=self.name,
            processor_version=self.version,
        )


def _validate_input_parts(
    ocr_result: OcrResult,
    selection_index: int,
    native_page: ExtractedPage | None,
    layout_result: PageLayoutResult | None,
    configuration: OCRReconciliationConfiguration,
) -> None:
    if not isinstance(ocr_result, OcrResult):
        raise TypeError("ocr_result must be OcrResult")
    _nonnegative_integer("selection_index", selection_index)
    if selection_index >= len(ocr_result.request.selections):
        raise ValueError("selection_index is outside the OCR result")
    if not isinstance(configuration, OCRReconciliationConfiguration):
        raise TypeError("configuration has the wrong type")
    selection = ocr_result.request.selections[selection_index]
    references = selection.native_text_blocks
    if bool(references) != (native_page is not None):
        raise ValueError(
            "native page is required exactly when native references exist"
        )
    if bool(references) != (layout_result is not None):
        raise ValueError(
            "layout result is required exactly when native references exist"
        )
    if native_page is None or layout_result is None:
        return
    if not isinstance(native_page, ExtractedPage):
        raise TypeError("native_page must be ExtractedPage")
    if not isinstance(layout_result, PageLayoutResult):
        raise TypeError("layout_result must be PageLayoutResult")
    region = selection.image.rendered_region
    if (
        layout_result.source_id != region.source_id
        or layout_result.source_blob_id != region.source_blob_id
        or layout_result.source_content_hash != region.source_content_hash
        or layout_result.page_index != region.page_index
    ):
        raise ValueError(
            "layout result does not match the rendered source page"
        )
    if (
        native_page.page_index != region.page_index
        or native_page.coordinate_system != region.coordinate_system
        or native_page.rotation_degrees != region.page_rotation_degrees
        or layout_result.page_width != native_page.width
        or layout_result.page_height != native_page.height
        or layout_result.coordinate_system != native_page.coordinate_system
        or layout_result.rotation_degrees != native_page.rotation_degrees
    ):
        raise ValueError("native page does not match the rendered source page")
    if len(native_page.blocks) > configuration.max_native_blocks:
        raise OCRReconciliationLimitError(
            "native page blocks exceed max_native_blocks"
        )
    raw_references = tuple(
        (block.block_id, block.kind, block.source_spans)
        for block in native_page.blocks
    )
    layout_references = tuple(
        (reference.block_id, reference.kind, reference.source_spans)
        for reference in layout_result.raw_blocks
    )
    if raw_references != layout_references:
        raise ValueError("layout result does not exactly reference native page")
    blocks = {block.block_id: block for block in native_page.blocks}
    if len(blocks) != len(native_page.blocks):
        raise ValueError("native page block IDs must be unique")
    total_text = 0
    for reference in references:
        block = blocks.get(reference.block_id)
        if block is None:
            raise ValueError("native OCR reference is unresolved")
        if block.kind != "text" or not isinstance(block.text, str):
            raise ValueError("native OCR reference is not text-bearing")
        if block.source_spans != next(
            item.source_spans
            for item in layout_result.raw_blocks
            if item.block_id == block.block_id
        ):
            raise ValueError("native OCR reference source spans are stale")
        _bounded_text(
            "native block text",
            block.text,
            limit=configuration.max_text_characters_per_item,
        )
        total_text += len(block.text)
        if total_text > configuration.max_total_text_characters:
            raise OCRReconciliationLimitError(
                "native text exceeds max_total_text_characters"
            )


def _input_id(
    ocr_result: OcrResult,
    selection_index: int,
    native_page: ExtractedPage | None,
    layout_result: PageLayoutResult | None,
    configuration: OCRReconciliationConfiguration,
) -> str:
    selected_blocks: tuple[object, ...] = ()
    if native_page is not None:
        selected_ids = set(
            ocr_result.request.selections[selection_index].native_text_block_ids
        )
        selected_blocks = tuple(
            (
                block.block_id,
                block.kind,
                block.text,
                tuple(span.identity_parts() for span in block.source_spans),
            )
            for block in native_page.blocks
            if block.block_id in selected_ids
        )
    return stable_id(
        "ocr-reconciliation-input",
        OCR_RECONCILIATION_CONTRACT_VERSION,
        ocr_result.result_id,
        selection_index,
        selected_blocks,
        layout_result.result_id if layout_result is not None else None,
        configuration.identity_parts(),
    )


def _native_stream(
    reconciliation_input: OCRReconciliationInput,
) -> tuple[OCRNativeBlockEvidence, ...]:
    if (
        reconciliation_input.native_page is None
        or reconciliation_input.layout_result is None
    ):
        return ()
    page = reconciliation_input.native_page
    layout = reconciliation_input.layout_result
    selected = set(reconciliation_input.selection.native_text_block_ids)
    raw_order = {
        block.block_id: index for index, block in enumerate(page.blocks)
    }
    proposed = {
        block_id: index for index, block_id in enumerate(layout.proposed_order)
    }
    block_by_id = {block.block_id: block for block in page.blocks}
    ordered_ids = sorted(
        selected,
        key=lambda block_id: (
            0 if block_id in proposed else 1,
            proposed.get(block_id, raw_order[block_id]),
            raw_order[block_id],
        ),
    )
    return tuple(
        OCRNativeBlockEvidence.from_block(block_by_id[block_id], order=order)
        for order, block_id in enumerate(ordered_ids)
    )


def _native_segments(
    native_stream: tuple[OCRNativeBlockEvidence, ...],
    configuration: OCRReconciliationConfiguration,
) -> tuple[OCRNativeLineSegment, ...]:
    segments: list[OCRNativeLineSegment] = []
    total_text = 0
    for block in native_stream:
        for line_index, raw_line in _iter_text_lines(block.text):
            if not raw_line.strip():
                continue
            _bounded_text(
                "native line text",
                raw_line,
                nonempty=True,
                limit=configuration.max_text_characters_per_item,
            )
            total_text += len(raw_line)
            if total_text > configuration.max_total_text_characters:
                raise OCRReconciliationLimitError(
                    "native segments exceed max_total_text_characters"
                )
            if len(segments) >= configuration.max_native_segments:
                raise OCRReconciliationLimitError(
                    "native segments exceed max_native_segments"
                )
            segment = OCRNativeLineSegment.create(
                block=block,
                line_index=line_index,
                text=raw_line,
                order=len(segments),
            )
            if (
                len(segment.normalized_text)
                > configuration.max_text_characters_per_item
            ):
                raise OCRReconciliationLimitError(
                    "normalized native text exceeds its configured limit"
                )
            segments.append(segment)
    return tuple(segments)


def _iter_text_lines(value: str) -> Iterator[tuple[int, str]]:
    if not value:
        yield 0, ""
        return
    start = 0
    line_index = 0
    position = 0
    while position < len(value):
        character = value[position]
        if character not in _LINE_BOUNDARIES:
            position += 1
            continue
        yield line_index, value[start:position]
        if (
            character == "\r"
            and position + 1 < len(value)
            and value[position + 1] == "\n"
        ):
            position += 1
        position += 1
        start = position
        line_index += 1
    if start < len(value):
        yield line_index, value[start:]


def _input_warnings(
    reconciliation_input: OCRReconciliationInput,
) -> list[OCRReconciliationWarning]:
    warnings: list[OCRReconciliationWarning] = []
    selection_result = reconciliation_input.selection_result
    if selection_result.status is not OCRSelectionStatus.COMPLETED:
        warnings.append(
            OCRReconciliationWarning.create(
                code="ocr.reconciliation.incomplete_ocr_stream",
                severity=WarningSeverity.WARNING,
                message=(
                    "OCR stream is partial or failed; reconciliation "
                    "is incomplete"
                ),
                object_ids=(selection_result.selection_result_id,),
                evidence=(("status", selection_result.status.value),),
            )
        )
    layout = reconciliation_input.layout_result
    if layout is not None and layout.warnings:
        warnings.append(
            OCRReconciliationWarning.create(
                code="ocr.reconciliation.uncertain_native_order",
                severity=WarningSeverity.WARNING,
                message=("Native reading order retains layout uncertainty"),
                object_ids=(layout.result_id,),
                evidence=(("layout_warning_count", str(len(layout.warnings))),),
            )
        )
    return warnings


def _candidates(
    native_segments: tuple[OCRNativeLineSegment, ...],
    ocr_lines: tuple[OCRLine, ...],
    configuration: OCRReconciliationConfiguration,
) -> tuple[list[_Candidate], list[OCRReconciliationWarning]]:
    if not native_segments or not ocr_lines:
        return [], []
    candidates: list[_Candidate] = []
    warnings: list[OCRReconciliationWarning] = []
    comparison_work = 0
    oversized: list[str] = []
    normalized_ocr: list[str | None] = []
    for line in ocr_lines:
        if len(line.text) > configuration.max_comparison_text_characters:
            oversized.append(line.line_id)
            normalized_ocr.append(None)
        else:
            normalized = _normalized_text(line.text)
            if len(normalized) > configuration.max_comparison_text_characters:
                oversized.append(line.line_id)
                normalized_ocr.append(None)
            else:
                normalized_ocr.append(normalized)
    for native in native_segments:
        if (
            len(native.normalized_text)
            > configuration.max_comparison_text_characters
        ):
            oversized.append(native.segment_id)
            continue
        for ocr_line, normalized_ocr_text in zip(
            ocr_lines, normalized_ocr, strict=True
        ):
            if not native.normalized_text or not normalized_ocr_text:
                continue
            overlap = _geometry_overlap(
                native.source_bounding_box,
                ocr_line.source_bounding_box,
            )
            if (
                overlap is not None
                and overlap < configuration.minimum_geometry_overlap
            ):
                continue
            comparison_work += min(
                len(native.normalized_text), len(normalized_ocr_text)
            )
            if comparison_work > configuration.max_comparison_work:
                raise OCRReconciliationLimitError(
                    "text comparison work exceeds max_comparison_work"
                )
            if native.normalized_text == normalized_ocr_text:
                similarity = 1.0
                kind = OCRReconciliationMatchKind.DUPLICATE
                score = 2.0 + (overlap or 0.0)
            else:
                if overlap is None:
                    continue
                comparison_work += len(native.normalized_text) * len(
                    normalized_ocr_text
                )
                if comparison_work > configuration.max_comparison_work:
                    raise OCRReconciliationLimitError(
                        "text comparison work exceeds max_comparison_work"
                    )
                similarity = SequenceMatcher(
                    None,
                    native.normalized_text,
                    normalized_ocr_text,
                    autojunk=False,
                ).ratio()
                if similarity < configuration.minimum_disagreement_similarity:
                    continue
                kind = OCRReconciliationMatchKind.DISAGREEMENT
                score = similarity + overlap
            candidates.append(
                _Candidate(
                    native_segment_id=native.segment_id,
                    ocr_line_id=ocr_line.line_id,
                    kind=kind,
                    text_similarity=similarity,
                    geometry_overlap=overlap,
                    score=score,
                    native_order=native.order,
                    ocr_order=ocr_line.order,
                )
            )
    if oversized:
        warnings.append(
            OCRReconciliationWarning.create(
                code="ocr.reconciliation.text_comparison_skipped",
                severity=WarningSeverity.WARNING,
                message="Oversized text evidence was not compared",
                object_ids=tuple(dict.fromkeys(oversized)),
                evidence=(),
            )
        )
    candidates.sort(
        key=lambda item: (
            -item.score,
            item.native_order,
            item.ocr_order,
            item.native_segment_id,
            item.ocr_line_id,
        )
    )
    return candidates, warnings


def _matches(
    candidates: list[_Candidate],
    configuration: OCRReconciliationConfiguration,
) -> tuple[list[_Candidate], list[OCRReconciliationWarning]]:
    by_native: dict[str, list[_Candidate]] = {}
    by_ocr: dict[str, list[_Candidate]] = {}
    for candidate in candidates:
        by_native.setdefault(candidate.native_segment_id, []).append(candidate)
        by_ocr.setdefault(candidate.ocr_line_id, []).append(candidate)
    ambiguous: set[str] = set()
    for candidate_group in (*by_native.values(), *by_ocr.values()):
        ordered = sorted(candidate_group, key=lambda item: -item.score)
        if (
            len(ordered) > 1
            and ordered[0].kind is ordered[1].kind
            and ordered[0].score - ordered[1].score
            <= configuration.ambiguity_score_delta
        ):
            ambiguous.update(
                (
                    ordered[0].native_segment_id,
                    ordered[0].ocr_line_id,
                    ordered[1].native_segment_id,
                    ordered[1].ocr_line_id,
                )
            )
    warnings: list[OCRReconciliationWarning] = []
    if ambiguous:
        warnings.append(
            OCRReconciliationWarning.create(
                code="ocr.reconciliation.ambiguous_match",
                severity=WarningSeverity.WARNING,
                message="Competing reconciliation matches are ambiguous",
                object_ids=tuple(sorted(ambiguous)),
                evidence=(
                    (
                        "ambiguity_score_delta",
                        str(configuration.ambiguity_score_delta),
                    ),
                ),
            )
        )
    used_native: set[str] = set()
    used_ocr: set[str] = set()
    selected: list[_Candidate] = []
    for candidate in candidates:
        if (
            candidate.native_segment_id in ambiguous
            or candidate.ocr_line_id in ambiguous
            or candidate.native_segment_id in used_native
            or candidate.ocr_line_id in used_ocr
        ):
            continue
        used_native.add(candidate.native_segment_id)
        used_ocr.add(candidate.ocr_line_id)
        selected.append(candidate)
    selected.sort(key=lambda item: (item.native_order, item.ocr_order))
    for candidate in selected:
        if candidate.kind is OCRReconciliationMatchKind.DISAGREEMENT:
            warnings.append(
                OCRReconciliationWarning.create(
                    code="ocr.reconciliation.text_disagreement",
                    severity=WarningSeverity.WARNING,
                    message="Native and OCR text evidence disagree",
                    object_ids=(
                        candidate.native_segment_id,
                        candidate.ocr_line_id,
                    ),
                    evidence=(
                        ("text_similarity", str(candidate.text_similarity)),
                        (
                            "geometry_overlap",
                            str(candidate.geometry_overlap),
                        ),
                    ),
                )
            )
    return selected, warnings


def _match_with_warning(
    candidate: _Candidate,
    warning_by_id: dict[str, OCRReconciliationWarning],
) -> OCRReconciliationMatch:
    warning_ids = tuple(
        warning.warning_id
        for warning in warning_by_id.values()
        if warning.code == "ocr.reconciliation.text_disagreement"
        and set(warning.object_ids)
        == {candidate.native_segment_id, candidate.ocr_line_id}
    )
    return OCRReconciliationMatch.create(
        kind=candidate.kind,
        native_segment_id=candidate.native_segment_id,
        ocr_line_id=candidate.ocr_line_id,
        text_similarity=candidate.text_similarity,
        geometry_overlap=candidate.geometry_overlap,
        warning_ids=warning_ids,
    )


def _merged_stream(
    native_segments: tuple[OCRNativeLineSegment, ...],
    ocr_lines: tuple[OCRLine, ...],
    matches: tuple[OCRReconciliationMatch, ...],
    warnings: tuple[OCRReconciliationWarning, ...],
) -> tuple[OCRReconciledItem, ...]:
    ocr_by_id = {item.line_id: item for item in ocr_lines}
    match_by_native = {item.native_segment_id: item for item in matches}
    matched_ocr = {item.ocr_line_id for item in matches}
    items: list[OCRReconciledItem] = []
    for native in native_segments:
        match = match_by_native.get(native.segment_id)
        if match is None:
            items.append(
                OCRReconciledItem.create(
                    kind=OCRReconciledItemKind.NATIVE_ONLY,
                    order=len(items),
                    native_segment_id=native.segment_id,
                    ocr_line_id=None,
                    proposed_text=native.text,
                    warning_ids=_warnings_for_object(
                        native.segment_id, warnings
                    ),
                )
            )
            continue
        ocr_line = ocr_by_id[match.ocr_line_id]
        if match.kind is OCRReconciliationMatchKind.DUPLICATE:
            items.append(
                OCRReconciledItem.create(
                    kind=OCRReconciledItemKind.DUPLICATE,
                    order=len(items),
                    native_segment_id=native.segment_id,
                    ocr_line_id=ocr_line.line_id,
                    proposed_text=native.text,
                )
            )
        else:
            items.append(
                OCRReconciledItem.create(
                    kind=OCRReconciledItemKind.DISAGREEMENT,
                    order=len(items),
                    native_segment_id=native.segment_id,
                    ocr_line_id=ocr_line.line_id,
                    proposed_text=None,
                    warning_ids=match.warning_ids,
                )
            )
    for ocr_line in ocr_lines:
        if ocr_line.line_id in matched_ocr:
            continue
        items.append(
            OCRReconciledItem.create(
                kind=OCRReconciledItemKind.OCR_ONLY,
                order=len(items),
                native_segment_id=None,
                ocr_line_id=ocr_line.line_id,
                proposed_text=ocr_line.text,
                warning_ids=_warnings_for_object(ocr_line.line_id, warnings),
            )
        )
    return tuple(items)


def _warnings_for_object(
    object_id: str,
    warnings: tuple[OCRReconciliationWarning, ...],
) -> tuple[str, ...]:
    return tuple(
        warning.warning_id
        for warning in warnings
        if object_id in warning.object_ids
        and warning.code != "ocr.reconciliation.text_disagreement"
    )


def _preflight_result_collections(
    reconciliation_input: OCRReconciliationInput,
    native_stream: tuple[OCRNativeBlockEvidence, ...],
    native_segments: tuple[OCRNativeLineSegment, ...],
    ocr_stream: tuple[OCRLine, ...],
    matches: tuple[OCRReconciliationMatch, ...],
    proposed_merged_stream: tuple[OCRReconciledItem, ...],
    warnings: tuple[OCRReconciliationWarning, ...],
) -> None:
    config = reconciliation_input.configuration
    for name, values, expected_type, maximum in (
        (
            "native_stream",
            native_stream,
            OCRNativeBlockEvidence,
            config.max_native_blocks,
        ),
        (
            "native_segments",
            native_segments,
            OCRNativeLineSegment,
            config.max_native_segments,
        ),
        ("ocr_stream", ocr_stream, OCRLine, config.max_ocr_lines),
        (
            "matches",
            matches,
            OCRReconciliationMatch,
            min(config.max_native_segments, config.max_ocr_lines),
        ),
        (
            "proposed_merged_stream",
            proposed_merged_stream,
            OCRReconciledItem,
            config.max_native_segments + config.max_ocr_lines,
        ),
        (
            "warnings",
            warnings,
            OCRReconciliationWarning,
            config.max_warnings,
        ),
    ):
        _require_tuple(name, values)
        if len(values) > maximum:
            raise OCRReconciliationLimitError(f"{name} exceeds its limit")
        if any(not isinstance(item, expected_type) for item in values):
            raise TypeError(f"{name} contains an unsupported value")


def _validate_result(result: OCRReconciliationResult) -> None:
    config = result.reconciliation_input.configuration
    _preflight_result_collections(
        result.reconciliation_input,
        result.native_stream,
        result.native_segments,
        result.ocr_stream,
        result.matches,
        result.proposed_merged_stream,
        result.warnings,
    )
    _bounded_string("result ID", result.result_id)
    _bounded_string("processor name", result.processor_name)
    _bounded_string("processor version", result.processor_version)
    if result.configuration_digest != config.configuration_digest:
        raise ValueError("reconciliation configuration digest is stale")
    if len(result.native_stream) > config.max_native_blocks:
        raise OCRReconciliationLimitError("native stream exceeds its limit")
    if len(result.native_segments) > config.max_native_segments:
        raise OCRReconciliationLimitError("native segments exceed their limit")
    if len(result.ocr_stream) > config.max_ocr_lines:
        raise OCRReconciliationLimitError("OCR stream exceeds its limit")
    if len(result.warnings) > config.max_warnings:
        raise OCRReconciliationLimitError("warnings exceed their limit")
    for name, values, identity_attribute in (
        ("native evidence", result.native_stream, "evidence_id"),
        ("native segments", result.native_segments, "segment_id"),
        ("OCR lines", result.ocr_stream, "line_id"),
        ("matches", result.matches, "match_id"),
        ("merged items", result.proposed_merged_stream, "item_id"),
        ("warnings", result.warnings, "warning_id"),
    ):
        identities = tuple(getattr(item, identity_attribute) for item in values)
        if len(set(identities)) != len(identities):
            raise ValueError(f"{name} IDs must be unique")
    if tuple(item.order for item in result.native_stream) != tuple(
        range(len(result.native_stream))
    ):
        raise ValueError("native stream order must be contiguous")
    if tuple(item.order for item in result.native_segments) != tuple(
        range(len(result.native_segments))
    ):
        raise ValueError("native segment order must be contiguous")
    if tuple(item.order for item in result.ocr_stream) != tuple(
        range(len(result.ocr_stream))
    ):
        raise ValueError("OCR stream order must be contiguous")
    if tuple(item.order for item in result.proposed_merged_stream) != tuple(
        range(len(result.proposed_merged_stream))
    ):
        raise ValueError("merged stream order must be contiguous")
    expected_native_stream = _native_stream(result.reconciliation_input)
    if result.native_stream != expected_native_stream:
        raise ValueError("native stream does not preserve exact block evidence")
    expected_native_segments = _native_segments(expected_native_stream, config)
    if result.native_segments != expected_native_segments:
        raise ValueError("native segments do not preserve exact text evidence")
    selected_result = result.reconciliation_input.selection_result
    if result.ocr_stream != selected_result.lines:
        raise ValueError("OCR stream does not preserve exact line evidence")
    warning_ids = {warning.warning_id for warning in result.warnings}
    segment_by_id = {
        segment.segment_id: segment for segment in result.native_segments
    }
    ocr_by_id = {line.line_id: line for line in result.ocr_stream}
    segment_ids = set(segment_by_id)
    ocr_ids = set(ocr_by_id)
    resolvable_warning_object_ids = (
        segment_ids
        | ocr_ids
        | {item.evidence_id for item in result.native_stream}
        | {item.block_id for item in result.native_stream}
        | {
            result.reconciliation_input.input_id,
            result.reconciliation_input.ocr_result.result_id,
            selected_result.selection_result_id,
        }
    )
    if result.reconciliation_input.layout_result is not None:
        resolvable_warning_object_ids.add(
            result.reconciliation_input.layout_result.result_id
        )
    for warning in result.warnings:
        if not set(warning.object_ids).issubset(resolvable_warning_object_ids):
            raise ValueError("warning has unresolved evidence objects")
    matched_native: set[str] = set()
    matched_ocr: set[str] = set()
    validation_comparison_work = 0
    for match in result.matches:
        if match.native_segment_id not in segment_ids:
            raise ValueError("match has unresolved native segment")
        if match.ocr_line_id not in ocr_ids:
            raise ValueError("match has unresolved OCR line")
        if match.native_segment_id in matched_native:
            raise ValueError("native segment has multiple matches")
        if match.ocr_line_id in matched_ocr:
            raise ValueError("OCR line has multiple matches")
        if not set(match.warning_ids).issubset(warning_ids):
            raise ValueError("match warning link is unresolved")
        native = segment_by_id[match.native_segment_id]
        ocr_line = ocr_by_id[match.ocr_line_id]
        if (
            len(native.normalized_text) > config.max_comparison_text_characters
            or len(ocr_line.text) > config.max_comparison_text_characters
        ):
            raise OCRReconciliationLimitError(
                "matched text exceeds max_comparison_text_characters"
            )
        normalized_ocr_text = _normalized_text(ocr_line.text)
        if len(normalized_ocr_text) > config.max_comparison_text_characters:
            raise OCRReconciliationLimitError(
                "normalized match text exceeds its comparison limit"
            )
        validation_comparison_work += min(
            len(native.normalized_text), len(normalized_ocr_text)
        )
        if match.kind is OCRReconciliationMatchKind.DISAGREEMENT:
            validation_comparison_work += len(native.normalized_text) * len(
                normalized_ocr_text
            )
        if validation_comparison_work > config.max_comparison_work:
            raise OCRReconciliationLimitError(
                "match validation exceeds max_comparison_work"
            )
        expected_overlap = _geometry_overlap(
            native.source_bounding_box, ocr_line.source_bounding_box
        )
        if match.geometry_overlap != expected_overlap:
            raise ValueError("match geometry overlap is inconsistent")
        if match.kind is OCRReconciliationMatchKind.DUPLICATE:
            if native.normalized_text != normalized_ocr_text:
                raise ValueError("duplicate match text is not equivalent")
            if (
                expected_overlap is not None
                and expected_overlap < config.minimum_geometry_overlap
            ):
                raise ValueError("duplicate match geometry is contradictory")
        else:
            expected_similarity = SequenceMatcher(
                None,
                native.normalized_text,
                normalized_ocr_text,
                autojunk=False,
            ).ratio()
            if match.text_similarity != expected_similarity:
                raise ValueError("disagreement similarity is inconsistent")
            if (
                expected_overlap is None
                or expected_overlap < config.minimum_geometry_overlap
                or expected_similarity < config.minimum_disagreement_similarity
            ):
                raise ValueError("disagreement match lacks sufficient evidence")
            if not any(
                warning.code == "ocr.reconciliation.text_disagreement"
                and warning.warning_id in match.warning_ids
                and set(warning.object_ids)
                == {match.native_segment_id, match.ocr_line_id}
                for warning in result.warnings
            ):
                raise ValueError(
                    "disagreement match lacks its specific warning"
                )
        matched_native.add(match.native_segment_id)
        matched_ocr.add(match.ocr_line_id)
    match_by_pair = {
        (match.native_segment_id, match.ocr_line_id): match
        for match in result.matches
    }
    covered_native: set[str] = set()
    covered_ocr: set[str] = set()
    for item in result.proposed_merged_stream:
        if item.native_segment_id is not None:
            if item.native_segment_id not in segment_ids:
                raise ValueError("merged item has unresolved native segment")
            if item.native_segment_id in covered_native:
                raise ValueError(
                    "native segment appears twice in merged stream"
                )
            covered_native.add(item.native_segment_id)
        if item.ocr_line_id is not None:
            if item.ocr_line_id not in ocr_ids:
                raise ValueError("merged item has unresolved OCR line")
            if item.ocr_line_id in covered_ocr:
                raise ValueError("OCR line appears twice in merged stream")
            covered_ocr.add(item.ocr_line_id)
        if not set(item.warning_ids).issubset(warning_ids):
            raise ValueError("merged item warning link is unresolved")
        merged_native = (
            segment_by_id[item.native_segment_id]
            if item.native_segment_id is not None
            else None
        )
        merged_ocr_line = (
            ocr_by_id[item.ocr_line_id]
            if item.ocr_line_id is not None
            else None
        )
        pair = (
            match_by_pair.get((item.native_segment_id, item.ocr_line_id))
            if item.native_segment_id is not None
            and item.ocr_line_id is not None
            else None
        )
        if item.kind is OCRReconciledItemKind.DUPLICATE:
            if (
                pair is None
                or pair.kind is not OCRReconciliationMatchKind.DUPLICATE
            ):
                raise ValueError("duplicate merged item lacks duplicate match")
            assert merged_native is not None
            if item.proposed_text != merged_native.text:
                raise ValueError("duplicate proposal must preserve native text")
        elif item.kind is OCRReconciledItemKind.DISAGREEMENT:
            if (
                pair is None
                or pair.kind is not OCRReconciliationMatchKind.DISAGREEMENT
                or item.warning_ids != pair.warning_ids
            ):
                raise ValueError(
                    "disagreement merged item lacks its exact match evidence"
                )
        elif item.kind is OCRReconciledItemKind.NATIVE_ONLY:
            assert merged_native is not None
            if (
                item.proposed_text != merged_native.text
                or merged_native.segment_id in matched_native
            ):
                raise ValueError("native-only proposal is inconsistent")
        else:
            assert merged_ocr_line is not None
            if (
                item.proposed_text != merged_ocr_line.text
                or merged_ocr_line.line_id in matched_ocr
            ):
                raise ValueError("OCR-only proposal is inconsistent")
    if covered_native != segment_ids or covered_ocr != ocr_ids:
        raise ValueError("merged stream must cover both original streams")
    _validate_retained_size(result, config.max_result_bytes)


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
            for field in fields(item):
                increment += len(field.name) + 3
                if isinstance(item, RenderedRegion) and field.name == "content":
                    continue
                stack.append(getattr(item, field.name))
        else:
            raise TypeError(
                "reconciliation result contains unsupported evidence"
            )
        total += increment
        if total > limit:
            raise OCRReconciliationLimitError(
                "reconciliation result exceeds max_result_bytes"
            )


def _native_block_evidence_id(block: ExtractedBlock, order: int) -> str:
    return stable_id(
        "ocr-native-block-evidence",
        OCR_RECONCILIATION_CONTRACT_VERSION,
        block.block_id,
        block.text,
        tuple(span.identity_parts() for span in block.source_spans),
        order,
    )


def _native_segment_id(
    block_evidence_id: str,
    block_id: str,
    line_index: int,
    text: str,
    normalized_text: str,
    source_bounding_box: BoundingBox | None,
    order: int,
) -> str:
    return stable_id(
        "ocr-native-line-segment",
        OCR_RECONCILIATION_CONTRACT_VERSION,
        block_evidence_id,
        block_id,
        line_index,
        text,
        normalized_text,
        source_bounding_box,
        order,
    )


def _warning_id(
    code: str,
    severity: WarningSeverity,
    message: str,
    object_ids: tuple[str, ...],
    evidence: Metadata,
) -> str:
    return stable_id(
        "ocr-reconciliation-warning",
        code,
        severity.value,
        message,
        object_ids,
        evidence,
    )


def _match_id(
    kind: OCRReconciliationMatchKind,
    native_segment_id: str,
    ocr_line_id: str,
    text_similarity: float,
    geometry_overlap: float | None,
    warning_ids: tuple[str, ...],
) -> str:
    return stable_id(
        "ocr-reconciliation-match",
        kind.value,
        native_segment_id,
        ocr_line_id,
        text_similarity,
        geometry_overlap,
        warning_ids,
    )


def _item_id(
    kind: OCRReconciledItemKind,
    order: int,
    native_segment_id: str | None,
    ocr_line_id: str | None,
    proposed_text: str | None,
    warning_ids: tuple[str, ...],
) -> str:
    return stable_id(
        "ocr-reconciled-item",
        kind.value,
        order,
        native_segment_id,
        ocr_line_id,
        proposed_text,
        warning_ids,
    )


def _result_id(
    input_id: str,
    native_stream: tuple[OCRNativeBlockEvidence, ...],
    native_segments: tuple[OCRNativeLineSegment, ...],
    ocr_stream: tuple[OCRLine, ...],
    matches: tuple[OCRReconciliationMatch, ...],
    proposed_stream: tuple[OCRReconciledItem, ...],
    warnings: tuple[OCRReconciliationWarning, ...],
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
) -> str:
    return stable_id(
        "ocr-reconciliation-result",
        OCR_RECONCILIATION_CONTRACT_VERSION,
        input_id,
        tuple(item.evidence_id for item in native_stream),
        tuple(item.segment_id for item in native_segments),
        tuple(item.line_id for item in ocr_stream),
        tuple(item.match_id for item in matches),
        tuple(item.item_id for item in proposed_stream),
        tuple(item.warning_id for item in warnings),
        processor_name,
        processor_version,
        configuration_digest,
    )


def _normalized_text(value: str) -> str:
    normalized = " ".join(
        unicodedata.normalize("NFKC", value).casefold().split()
    )
    if len(normalized) > _MAX_TEXT_CHARACTERS_PER_ITEM:
        raise OCRReconciliationLimitError(
            "normalized text exceeds the implementation maximum"
        )
    return normalized


def _spans_bounding_box(
    source_spans: tuple[SourceSpan, ...],
) -> BoundingBox | None:
    boxes = tuple(
        span.bounding_box
        for span in source_spans
        if span.bounding_box is not None
    )
    if len(boxes) != len(source_spans) or not boxes:
        return None
    return _validated_box(
        (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
    )


def _geometry_overlap(
    first: BoundingBox | None, second: BoundingBox | None
) -> float | None:
    if first is None or second is None:
        return None
    x0 = max(first[0], second[0])
    y0 = max(first[1], second[1])
    x1 = min(first[2], second[2])
    y1 = min(first[3], second[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    intersection = (x1 - x0) * (y1 - y0)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    overlap = intersection / min(first_area, second_area)
    return _unit_float("geometry overlap", min(1.0, max(0.0, overlap)))


def _validated_box(value: BoundingBox) -> BoundingBox:
    if not isinstance(value, tuple) or len(value) != 4:
        raise TypeError("bounding box must be an immutable four-tuple")
    coordinates: list[float] = []
    for coordinate in value:
        if isinstance(coordinate, bool) or not isinstance(
            coordinate, int | float
        ):
            raise ValueError("bounding box coordinates must be finite")
        normalized = float(coordinate)
        if not math.isfinite(normalized):
            raise ValueError("bounding box coordinates must be finite")
        coordinates.append(0.0 if normalized == 0.0 else normalized)
    x0, y0, x1, y1 = coordinates
    if x1 <= x0 or y1 <= y0:
        raise ValueError("bounding box must have positive area")
    return (x0, y0, x1, y1)


def _unit_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a finite number")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{name} must be between zero and one")
    return 0.0 if normalized == 0.0 else normalized


def _validate_metadata(value: Metadata) -> None:
    _require_tuple("warning evidence", value)
    if len(value) > _MAX_WARNING_EVIDENCE_ENTRIES:
        raise OCRReconciliationLimitError(
            "warning evidence exceeds the entry limit"
        )
    total_characters = 0
    for entry in value:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("warning evidence must contain immutable pairs")
        _bounded_string("warning evidence key", entry[0])
        _bounded_text("warning evidence value", entry[1])
        total_characters += len(entry[0]) + len(entry[1])
        if total_characters > _MAX_WARNING_EVIDENCE_CHARACTERS:
            raise OCRReconciliationLimitError(
                "warning evidence exceeds the character limit"
            )


def _require_unique_strings(
    name: str, values: tuple[str, ...], required: bool = False
) -> None:
    _require_tuple(name, values)
    if len(values) > _MAX_LINKED_IDS:
        raise OCRReconciliationLimitError(f"{name} exceeds the linked-ID limit")
    if required and not values:
        raise ValueError(f"{name} must be non-empty")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")
    for value in values:
        _bounded_string(name, value)


def _require_tuple(name: str, value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be an immutable tuple")


def _bounded_string(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or len(value) > _MAX_IDENTITY_CHARACTERS:
        raise ValueError(
            f"{name} must contain 1 to {_MAX_IDENTITY_CHARACTERS} characters"
        )
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _bounded_text(
    name: str,
    value: object,
    *,
    nonempty: bool = False,
    limit: int = _MAX_TEXT_CHARACTERS_PER_ITEM,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if nonempty and not value:
        raise ValueError(f"{name} must be non-empty")
    if len(value) > limit:
        raise OCRReconciliationLimitError(f"{name} exceeds its limit")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _positive_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _nonnegative_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")

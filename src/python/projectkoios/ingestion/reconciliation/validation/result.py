"""Cross-object reconciliation result validation."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from difflib import SequenceMatcher
from enum import Enum
from typing import TYPE_CHECKING

from projectkoios.ingestion.ocr.line import OCRLine
from projectkoios.ingestion.pdf.models import RenderedRegion
from projectkoios.ingestion.reconciliation.limit.error import (
    OCRReconciliationLimitError,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.reconciliation.evidence.native.block import (
        OCRNativeBlockEvidence,
    )
    from projectkoios.ingestion.reconciliation.item import (
        OCRReconciledItem,
    )
    from projectkoios.ingestion.reconciliation.match import (
        OCRReconciliationMatch,
    )
    from projectkoios.ingestion.reconciliation.request import (
        OCRReconciliationRequest,
    )
    from projectkoios.ingestion.reconciliation.result import (
        OCRReconciliationResult,
    )
    from projectkoios.ingestion.reconciliation.segment.native.line import (
        OCRNativeLineSegment,
    )
    from projectkoios.ingestion.reconciliation.warning import (
        OCRReconciliationWarning,
    )
from projectkoios.ingestion.reconciliation.derivation import (
    native as native_derivation,
)
from projectkoios.ingestion.reconciliation.geometry import analysis as geometry
from projectkoios.ingestion.reconciliation.validation import value as primitives


def _preflight_result_collections(
    reconciliation_input: OCRReconciliationRequest,
    native_stream: tuple[OCRNativeBlockEvidence, ...],
    native_segments: tuple[OCRNativeLineSegment, ...],
    ocr_stream: tuple[OCRLine, ...],
    matches: tuple[OCRReconciliationMatch, ...],
    proposed_merged_stream: tuple[OCRReconciledItem, ...],
    warnings: tuple[OCRReconciliationWarning, ...],
) -> None:
    from projectkoios.ingestion.reconciliation.evidence.native.block import (
        OCRNativeBlockEvidence,
    )
    from projectkoios.ingestion.reconciliation.item import (
        OCRReconciledItem,
    )
    from projectkoios.ingestion.reconciliation.match import (
        OCRReconciliationMatch,
    )
    from projectkoios.ingestion.reconciliation.segment.native.line import (
        OCRNativeLineSegment,
    )
    from projectkoios.ingestion.reconciliation.warning import (
        OCRReconciliationWarning,
    )

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
        primitives._require_tuple(name, values)
        if len(values) > maximum:
            raise OCRReconciliationLimitError(f"{name} exceeds its limit")
        if any(not isinstance(item, expected_type) for item in values):
            raise TypeError(f"{name} contains an unsupported value")


def _validate_result(result: OCRReconciliationResult) -> None:
    from projectkoios.ingestion.reconciliation.kind.item import (
        OCRReconciledItemKind,
    )
    from projectkoios.ingestion.reconciliation.kind.match import (
        OCRReconciliationMatchKind,
    )

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
    primitives._bounded_string("result ID", result.result_id)
    primitives._bounded_string("processor name", result.processor_name)
    primitives._bounded_string("processor version", result.processor_version)
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
    expected_native_stream = native_derivation._native_stream(
        result.reconciliation_input
    )
    if result.native_stream != expected_native_stream:
        raise ValueError("native stream does not preserve exact block evidence")
    expected_native_segments = native_derivation._native_segments(
        expected_native_stream, config
    )
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
        normalized_ocr_text = geometry._normalized_text(ocr_line.text)
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
        expected_overlap = geometry._geometry_overlap(
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

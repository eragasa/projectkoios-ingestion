"""Private deterministic native/OCR reconciliation derivation."""

from __future__ import annotations

from collections.abc import Iterator
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from projectkoios.ingestion.models import (
    WarningSeverity,
)
from projectkoios.ingestion.ocr.line import OCRLine
from projectkoios.ingestion.ocr.selection_status import OCRSelectionStatus
from projectkoios.ingestion.reconciliation._limits import (
    _LINE_BOUNDARIES,
)
from projectkoios.ingestion.reconciliation.limit_error import (
    OCRReconciliationLimitError,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.reconciliation._candidate import _Candidate
    from projectkoios.ingestion.reconciliation.configuration import (
        OCRReconciliationConfiguration,
    )
    from projectkoios.ingestion.reconciliation.item import OCRReconciledItem
    from projectkoios.ingestion.reconciliation.match import (
        OCRReconciliationMatch,
    )
    from projectkoios.ingestion.reconciliation.native_block_evidence import (
        OCRNativeBlockEvidence,
    )
    from projectkoios.ingestion.reconciliation.native_line_segment import (
        OCRNativeLineSegment,
    )
    from projectkoios.ingestion.reconciliation.request import (
        OCRReconciliationRequest,
    )
    from projectkoios.ingestion.reconciliation.warning import (
        OCRReconciliationWarning,
    )
from projectkoios.ingestion.reconciliation import _geometry as geometry
from projectkoios.ingestion.reconciliation import _primitives as primitives


def _native_stream(
    reconciliation_input: OCRReconciliationRequest,
) -> tuple[OCRNativeBlockEvidence, ...]:
    from projectkoios.ingestion.reconciliation.native_block_evidence import (
        OCRNativeBlockEvidence,
    )

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
    from projectkoios.ingestion.reconciliation.native_line_segment import (
        OCRNativeLineSegment,
    )

    segments: list[OCRNativeLineSegment] = []
    total_text = 0
    for block in native_stream:
        for (
            line_index,
            raw_line,
        ) in _iter_text_lines(block.text):
            if not raw_line.strip():
                continue
            primitives._bounded_text(
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
    reconciliation_input: OCRReconciliationRequest,
) -> list[OCRReconciliationWarning]:
    from projectkoios.ingestion.reconciliation.warning import (
        OCRReconciliationWarning,
    )

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
    from projectkoios.ingestion.reconciliation._candidate import _Candidate
    from projectkoios.ingestion.reconciliation.match_kind import (
        OCRReconciliationMatchKind,
    )
    from projectkoios.ingestion.reconciliation.warning import (
        OCRReconciliationWarning,
    )

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
            normalized = geometry._normalized_text(line.text)
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
            overlap = geometry._geometry_overlap(
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
    from projectkoios.ingestion.reconciliation.match_kind import (
        OCRReconciliationMatchKind,
    )
    from projectkoios.ingestion.reconciliation.warning import (
        OCRReconciliationWarning,
    )

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
    from projectkoios.ingestion.reconciliation.match import (
        OCRReconciliationMatch,
    )

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
    from projectkoios.ingestion.reconciliation.item import OCRReconciledItem
    from projectkoios.ingestion.reconciliation.item_kind import (
        OCRReconciledItemKind,
    )
    from projectkoios.ingestion.reconciliation.match_kind import (
        OCRReconciliationMatchKind,
    )

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

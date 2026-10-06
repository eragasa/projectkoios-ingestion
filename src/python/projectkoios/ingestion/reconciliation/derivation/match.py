"""Deterministic native/OCR match derivation."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from projectkoios.ingestion.models import (
    WarningSeverity,
)
from projectkoios.ingestion.ocr.line import OCRLine
from projectkoios.ingestion.reconciliation.limit.error import (
    OCRReconciliationLimitError,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.reconciliation.candidate.model import _Candidate
    from projectkoios.ingestion.reconciliation.configuration import (
        OCRReconciliationConfiguration,
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
from projectkoios.ingestion.reconciliation.geometry import analysis as geometry


def _candidates(
    native_segments: tuple[OCRNativeLineSegment, ...],
    ocr_lines: tuple[OCRLine, ...],
    configuration: OCRReconciliationConfiguration,
) -> tuple[list[_Candidate], list[OCRReconciliationWarning]]:
    from projectkoios.ingestion.reconciliation.candidate.model import _Candidate
    from projectkoios.ingestion.reconciliation.kind.match import (
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
    from projectkoios.ingestion.reconciliation.kind.match import (
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

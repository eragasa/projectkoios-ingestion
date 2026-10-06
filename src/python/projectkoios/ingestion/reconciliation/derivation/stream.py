"""Deterministic proposed merged-stream derivation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectkoios.ingestion.ocr.line import OCRLine

if TYPE_CHECKING:
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


def _merged_stream(
    native_segments: tuple[OCRNativeLineSegment, ...],
    ocr_lines: tuple[OCRLine, ...],
    matches: tuple[OCRReconciliationMatch, ...],
    warnings: tuple[OCRReconciliationWarning, ...],
) -> tuple[OCRReconciledItem, ...]:
    from projectkoios.ingestion.reconciliation.item import (
        OCRReconciledItem,
    )
    from projectkoios.ingestion.reconciliation.kind.item import (
        OCRReconciledItemKind,
    )
    from projectkoios.ingestion.reconciliation.kind.match import (
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

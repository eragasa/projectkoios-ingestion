"""Private stable-identity helpers for native/OCR reconciliation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedBlock,
    ExtractedPage,
    Metadata,
    WarningSeverity,
)
from projectkoios.ingestion.ocr.line import OCRLine
from projectkoios.ingestion.ocr.result.ocr import OCRResult
from projectkoios.ingestion.reconciliation.constants import (
    OCR_RECONCILIATION_CONTRACT_VERSION,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.reconciliation.configuration import (
        OCRReconciliationConfiguration,
    )
    from projectkoios.ingestion.reconciliation.evidence.native.block import (
        OCRNativeBlockEvidence,
    )
    from projectkoios.ingestion.reconciliation.item import (
        OCRReconciledItem,
    )
    from projectkoios.ingestion.reconciliation.kind.item import (
        OCRReconciledItemKind,
    )
    from projectkoios.ingestion.reconciliation.kind.match import (
        OCRReconciliationMatchKind,
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


def _input_id(
    ocr_result: OCRResult,
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

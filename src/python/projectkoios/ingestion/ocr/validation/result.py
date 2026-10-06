"""Cross-object aggregate OCR result validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectkoios.ingestion.ocr.limit.error import OCRContractLimitError

if TYPE_CHECKING:
    from projectkoios.ingestion.ocr.request import OCRRequest
    from projectkoios.ingestion.ocr.result.selection import OCRSelectionResult
    from projectkoios.ingestion.ocr.status.result import OCRResultStatus


def _preflight_result_counts(
    request: OCRRequest,
    selection_results: tuple[OCRSelectionResult, ...],
) -> None:
    from projectkoios.ingestion.ocr.result.selection import OCRSelectionResult

    configuration = request.configuration
    if any(
        not isinstance(item, OCRSelectionResult) for item in selection_results
    ):
        raise TypeError(
            "selection_results must contain OCRSelectionResult values"
        )
    if len(selection_results) != len(request.selections):
        raise ValueError("every OCR selection must have exactly one result")
    total_tokens = sum(len(item.tokens) for item in selection_results)
    total_lines = sum(len(item.lines) for item in selection_results)
    total_warnings = sum(len(item.warnings) for item in selection_results)
    if total_tokens > configuration.max_total_tokens:
        raise OCRContractLimitError("token count exceeds max_total_tokens")
    if total_lines > configuration.max_total_lines:
        raise OCRContractLimitError("line count exceeds max_total_lines")
    if total_warnings > configuration.max_total_warnings:
        raise OCRContractLimitError("warning count exceeds max_total_warnings")


def _overall_status(
    selection_results: tuple[OCRSelectionResult, ...],
) -> OCRResultStatus:
    from projectkoios.ingestion.ocr.status.result import OCRResultStatus
    from projectkoios.ingestion.ocr.status.selection import OCRSelectionStatus

    if not selection_results:
        raise ValueError("OCR result requires selection results")
    if all(
        item.status is OCRSelectionStatus.COMPLETED
        for item in selection_results
    ):
        return OCRResultStatus.COMPLETED
    if all(
        item.status is OCRSelectionStatus.FAILED for item in selection_results
    ):
        return OCRResultStatus.FAILED
    return OCRResultStatus.PARTIAL

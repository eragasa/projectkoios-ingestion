"""Private stable-identity helpers for OCR evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    BoundingBox,
    Metadata,
    WarningSeverity,
)
from projectkoios.ingestion.ocr.constants import (
    OCR_CONTRACT_VERSION,
    PIXEL_COORDINATE_SYSTEM,
)
from projectkoios.ingestion.pdf.models import (
    PYMUPDF_COORDINATE_SYSTEM,
    RenderedRegion,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.ocr.confidence import OCRConfidence
    from projectkoios.ingestion.ocr.configuration import OCRConfiguration
    from projectkoios.ingestion.ocr.failure import OCRFailure
    from projectkoios.ingestion.ocr.failure_kind import OCRFailureKind
    from projectkoios.ingestion.ocr.line import OCRLine
    from projectkoios.ingestion.ocr.native_text_block_reference import (
        OCRNativeTextBlockReference,
    )
    from projectkoios.ingestion.ocr.page_image import OCRPageImage
    from projectkoios.ingestion.ocr.request import OCRRequest
    from projectkoios.ingestion.ocr.result_status import OCRResultStatus
    from projectkoios.ingestion.ocr.selection import OCRSelection
    from projectkoios.ingestion.ocr.selection_result import OCRSelectionResult
    from projectkoios.ingestion.ocr.selection_status import OCRSelectionStatus
    from projectkoios.ingestion.ocr.token import OCRToken
    from projectkoios.ingestion.ocr.warning import OCRWarning


def _image_identity_parts(region: RenderedRegion) -> tuple[object, ...]:
    return (
        region.region_id,
        region.source_id,
        region.source_blob_id,
        region.source_content_hash,
        region.page_index,
        region.source_bounding_box,
        region.effective_source_bounding_box,
        region.pixel_to_source_matrix,
        region.pixel_rounding,
        region.page_rotation_degrees,
        region.selection_was_full_page,
        region.coordinate_system,
        region.resolution_dpi,
        region.color_mode.value,
        region.alpha,
        region.media_type,
        region.byte_length,
        region.width_pixels,
        region.height_pixels,
        region.content_sha256,
        region.processor_name,
        region.processor_version,
        region.backend_name,
        region.backend_version,
        region.configuration_digest,
    )


def _ocr_image_id(region: RenderedRegion) -> str:
    return stable_id(
        "ocr-image",
        OCR_CONTRACT_VERSION,
        _image_identity_parts(region),
    )


def _ocr_selection_id(
    image: OCRPageImage,
    native_text_blocks: tuple[OCRNativeTextBlockReference, ...],
) -> str:

    return stable_id(
        "ocr-selection",
        OCR_CONTRACT_VERSION,
        image.identity_parts(),
        tuple(item.identity_parts() for item in native_text_blocks),
    )


def _ocr_request_id(
    selections: tuple[OCRSelection, ...], configuration: OCRConfiguration
) -> str:

    return stable_id(
        "ocr-request",
        OCR_CONTRACT_VERSION,
        tuple(selection.identity_parts() for selection in selections),
        configuration.identity_parts(),
    )


def _ocr_warning_id(
    selection_id: str,
    code: str,
    severity: WarningSeverity,
    message: str,
    evidence: Metadata,
) -> str:
    return stable_id(
        "ocr-warning", selection_id, code, severity.value, message, evidence
    )


def _ocr_failure_id(
    selection_id: str,
    kind: OCRFailureKind,
    message: str,
    retryable: bool,
    warning_ids: tuple[str, ...],
) -> str:

    return stable_id(
        "ocr-failure",
        selection_id,
        kind.value,
        message,
        retryable,
        warning_ids,
    )


def _ocr_token_id(
    selection_id: str,
    image_id: str,
    text: str,
    pixel_box: BoundingBox,
    source_box: BoundingBox,
    confidence: OCRConfidence | None,
    order: int,
    line_order: int | None,
    warning_ids: tuple[str, ...],
    configuration_digest: str,
    processor_name: str,
    processor_version: str,
    backend_name: str,
    backend_version: str,
) -> str:

    return stable_id(
        "ocr-token",
        selection_id,
        image_id,
        PIXEL_COORDINATE_SYSTEM,
        PYMUPDF_COORDINATE_SYSTEM,
        text,
        pixel_box,
        source_box,
        confidence,
        order,
        line_order,
        warning_ids,
        configuration_digest,
        processor_name,
        processor_version,
        backend_name,
        backend_version,
    )


def _ocr_line_id(
    selection_id: str,
    image_id: str,
    text: str,
    pixel_box: BoundingBox,
    source_box: BoundingBox,
    confidence: OCRConfidence | None,
    order: int,
    token_ids: tuple[str, ...],
    warning_ids: tuple[str, ...],
    configuration_digest: str,
    processor_name: str,
    processor_version: str,
    backend_name: str,
    backend_version: str,
) -> str:

    return stable_id(
        "ocr-line",
        selection_id,
        image_id,
        PIXEL_COORDINATE_SYSTEM,
        PYMUPDF_COORDINATE_SYSTEM,
        text,
        pixel_box,
        source_box,
        confidence,
        order,
        token_ids,
        warning_ids,
        configuration_digest,
        processor_name,
        processor_version,
        backend_name,
        backend_version,
    )


def _ocr_selection_result_id(
    selection_id: str,
    image_id: str,
    status: OCRSelectionStatus,
    tokens: tuple[OCRToken, ...],
    lines: tuple[OCRLine, ...],
    warnings: tuple[OCRWarning, ...],
    failure: OCRFailure | None,
    configuration_digest: str,
    processor_name: str,
    processor_version: str,
    backend_name: str,
    backend_version: str,
) -> str:

    return stable_id(
        "ocr-selection-result",
        OCR_CONTRACT_VERSION,
        selection_id,
        image_id,
        status.value,
        tuple(token.token_id for token in tokens),
        tuple(line.line_id for line in lines),
        tuple(warning.warning_id for warning in warnings),
        failure.failure_id if failure is not None else None,
        configuration_digest,
        processor_name,
        processor_version,
        backend_name,
        backend_version,
    )


def _ocr_result_id(
    request: OCRRequest,
    selection_results: tuple[OCRSelectionResult, ...],
    status: OCRResultStatus,
    cache_key: str,
    processor_name: str,
    processor_version: str,
    backend_name: str,
    backend_version: str,
) -> str:

    return stable_id(
        "ocr-result",
        OCR_CONTRACT_VERSION,
        request.request_id,
        tuple(item.selection_result_id for item in selection_results),
        status.value,
        cache_key,
        processor_name,
        processor_version,
        backend_name,
        backend_version,
    )

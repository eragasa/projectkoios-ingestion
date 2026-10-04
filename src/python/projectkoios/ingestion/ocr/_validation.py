"""Private cross-object validation helpers for OCR evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedPage,
)
from projectkoios.ingestion.ocr._limits import (
    _MAX_NATIVE_PAGE_BLOCKS,
    _MAX_NATIVE_PAGE_SOURCE_SPANS,
)
from projectkoios.ingestion.ocr.base import OCRTextOutput
from projectkoios.ingestion.ocr.limit_error import OCRContractLimitError

if TYPE_CHECKING:
    from projectkoios.ingestion.ocr.configuration import OCRConfiguration
    from projectkoios.ingestion.ocr.native_text_block_reference import (
        OCRNativeTextBlockReference,
    )
    from projectkoios.ingestion.ocr.page_image import OCRPageImage
    from projectkoios.ingestion.ocr.request import OCRRequest
    from projectkoios.ingestion.ocr.result_status import OCRResultStatus
    from projectkoios.ingestion.ocr.selection import OCRSelection
    from projectkoios.ingestion.ocr.selection_result import OCRSelectionResult
from projectkoios.ingestion.ocr import _geometry as geometry
from projectkoios.ingestion.ocr import _primitives as primitives


def _native_text_references(
    image: OCRPageImage,
    page: ExtractedPage,
    block_ids: tuple[str, ...],
) -> tuple[OCRNativeTextBlockReference, ...]:
    from projectkoios.ingestion.ocr.native_text_block_reference import (
        OCRNativeTextBlockReference,
    )

    if not isinstance(page, ExtractedPage):
        raise TypeError("native_text_page must be an ExtractedPage")
    region = image.rendered_region
    if page.page_index != region.page_index:
        raise ValueError("native text page does not match rendered page")
    primitives._require_tuple("native text page blocks", page.blocks)
    if len(page.blocks) > _MAX_NATIVE_PAGE_BLOCKS:
        raise OCRContractLimitError(
            "native text page exceeds the block safety limit"
        )
    span_count = sum(len(block.source_spans) for block in page.blocks)
    if span_count > _MAX_NATIVE_PAGE_SOURCE_SPANS:
        raise OCRContractLimitError(
            "native text page exceeds the source-span safety limit"
        )
    blocks_by_id: dict[str, ExtractedBlock] = {}
    for block in page.blocks:
        primitives._hard_bounded_string(
            "native block ID", block.block_id, nonempty=True
        )
        if block.block_id in blocks_by_id:
            raise ValueError("native text page block IDs must be unique")
        blocks_by_id[block.block_id] = block
    references: list[OCRNativeTextBlockReference] = []
    for block_id in block_ids:
        referenced_block = blocks_by_id.get(block_id)
        if referenced_block is None:
            raise ValueError("native text block ID does not exist on the page")
        if referenced_block.kind != "text" or not isinstance(
            referenced_block.text, str
        ):
            raise ValueError(
                "native coexistence evidence must be text-bearing blocks"
            )
        if not referenced_block.source_spans:
            raise ValueError("native text block must retain source spans")
        if any(
            span.source_id != region.source_id
            or span.source_blob_id != region.source_blob_id
            or span.page_index != region.page_index
            for span in referenced_block.source_spans
        ):
            raise ValueError(
                "native text block must refer to the rendered source page"
            )
        references.append(
            OCRNativeTextBlockReference(
                block_id=referenced_block.block_id,
                source_id=region.source_id,
                source_blob_id=region.source_blob_id,
                page_index=region.page_index,
            )
        )
    return tuple(references)


def _preflight_request(
    selections: tuple[OCRSelection, ...], configuration: OCRConfiguration
) -> None:
    from projectkoios.ingestion.ocr.selection import OCRSelection

    if not selections:
        raise ValueError("an OCR request requires at least one selection")
    if len(selections) > configuration.max_selections:
        raise OCRContractLimitError("selection count exceeds max_selections")
    if configuration.max_total_warnings < len(selections):
        raise OCRContractLimitError(
            "max_total_warnings must allow one failure warning per selection"
        )
    if any(not isinstance(item, OCRSelection) for item in selections):
        raise TypeError("request selections must be OCRSelection values")
    selection_ids = tuple(selection.selection_id for selection in selections)
    if len(set(selection_ids)) != len(selection_ids):
        raise ValueError("OCR selection IDs must be unique")
    image_by_id = {
        selection.image.image_id: selection.image for selection in selections
    }
    if len(image_by_id) > configuration.max_images:
        raise OCRContractLimitError("image count exceeds max_images")

    total_pixels = 0
    total_bytes = 0
    total_identity_characters = 0
    for selection in selections:
        region = selection.image.rendered_region
        identity_strings = (
            selection.selection_id,
            selection.image.image_id,
            region.region_id,
            region.source_id,
            region.source_blob_id,
            region.source_content_hash,
            region.content_sha256,
            region.coordinate_system,
            region.pixel_rounding,
            region.media_type,
            region.processor_name,
            region.processor_version,
            region.backend_name,
            region.backend_version,
            region.configuration_digest,
            *(
                (region.printed_page_label,)
                if region.printed_page_label is not None
                else ()
            ),
            *selection.native_text_block_ids,
        )
        for value in identity_strings:
            primitives._bounded_string(
                "OCR identity field",
                value,
                configuration.max_identity_field_characters,
                nonempty=True,
            )
            total_identity_characters += len(value)
            if (
                total_identity_characters
                > configuration.max_total_identity_characters
            ):
                raise OCRContractLimitError(
                    "identity characters exceed max_total_identity_characters"
                )
    for image in image_by_id.values():
        region = image.rendered_region
        pixels = region.width_pixels * region.height_pixels
        if pixels > configuration.max_pixels_per_image:
            raise OCRContractLimitError(
                "image pixels exceed max_pixels_per_image"
            )
        if region.byte_length > configuration.max_bytes_per_image:
            raise OCRContractLimitError(
                "image bytes exceed max_bytes_per_image"
            )
        total_pixels += pixels
        total_bytes += region.byte_length
    if total_pixels > configuration.max_total_pixels:
        raise OCRContractLimitError("image pixels exceed max_total_pixels")
    if total_bytes > configuration.max_total_image_bytes:
        raise OCRContractLimitError("image bytes exceed max_total_image_bytes")


def _preflight_result_counts(
    request: OCRRequest,
    selection_results: tuple[OCRSelectionResult, ...],
) -> None:
    from projectkoios.ingestion.ocr.selection_result import OCRSelectionResult

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


def _validate_selection_result_intrinsic(
    result: OCRSelectionResult,
) -> None:
    from projectkoios.ingestion.ocr.selection_status import OCRSelectionStatus

    token_ids = tuple(item.token_id for item in result.tokens)
    line_ids = tuple(item.line_id for item in result.lines)
    warning_ids = tuple(item.warning_id for item in result.warnings)
    if len(set(token_ids)) != len(token_ids):
        raise ValueError("OCR token IDs must be unique")
    if len(set(line_ids)) != len(line_ids):
        raise ValueError("OCR line IDs must be unique")
    if len(set(warning_ids)) != len(warning_ids):
        raise ValueError("OCR warning IDs must be unique")
    if tuple(item.order for item in result.tokens) != tuple(
        range(len(result.tokens))
    ):
        raise ValueError("OCR token order must be contiguous and ordered")
    if tuple(item.order for item in result.lines) != tuple(
        range(len(result.lines))
    ):
        raise ValueError("OCR line order must be contiguous and ordered")
    for warning in result.warnings:
        if warning.selection_id != result.selection_id:
            raise ValueError("OCR warning refers to the wrong selection")
    outputs: tuple[OCRTextOutput, ...] = (
        *result.tokens,
        *result.lines,
    )
    for output in outputs:
        if output.selection_id != result.selection_id:
            raise ValueError("OCR output refers to the wrong selection")
        if output.image_id != result.image_id:
            raise ValueError("OCR output refers to the wrong image")
        if output.configuration_digest != result.configuration_digest:
            raise ValueError("OCR output configuration is stale")
        primitives._same_processor_identity(result, output)
        if not set(output.warning_ids).issubset(warning_ids):
            raise ValueError("OCR output warning links are unresolved")
    if result.status is OCRSelectionStatus.COMPLETED:
        if result.failure is not None:
            raise ValueError("completed OCR selection cannot have a failure")
    elif result.status is OCRSelectionStatus.PARTIAL:
        if result.failure is None or not result.warnings:
            raise ValueError(
                "partial OCR selection requires failure and warning evidence"
            )
        if not result.tokens and not result.lines:
            raise ValueError("partial OCR selection requires usable output")
    elif result.status is OCRSelectionStatus.FAILED:
        if result.tokens or result.lines:
            raise ValueError("failed OCR selection cannot contain output")
        if result.failure is None or not result.warnings:
            raise ValueError(
                "failed OCR selection requires failure and warning evidence"
            )
    if result.failure is not None:
        if result.failure.selection_id != result.selection_id:
            raise ValueError("OCR failure refers to the wrong selection")
        if not set(result.failure.warning_ids).issubset(warning_ids):
            raise ValueError("OCR failure warning links are unresolved")
    memberships = tuple(
        token_id for line in result.lines for token_id in line.token_ids
    )
    if memberships or (result.tokens and result.lines):
        if len(set(memberships)) != len(memberships):
            raise ValueError("OCR tokens must belong to at most one line")
        if set(memberships) != set(token_ids):
            raise ValueError("token and line membership must be complete")
        token_by_id = {token.token_id: token for token in result.tokens}
        for line in result.lines:
            for token_id in line.token_ids:
                token = token_by_id[token_id]
                if token.line_order != line.order:
                    raise ValueError("token line membership is contradictory")


def _validate_selection_result(
    result: OCRSelectionResult,
    selection: OCRSelection,
    configuration: OCRConfiguration,
) -> None:
    from projectkoios.ingestion.ocr.output_mode import OCROutputMode
    from projectkoios.ingestion.ocr.selection_status import OCRSelectionStatus

    _validate_selection_result_intrinsic(result)
    if result.selection_id != selection.selection_id:
        raise ValueError("selection result refers to the wrong selection")
    if result.image_id != selection.image.image_id:
        raise ValueError("selection result refers to the wrong image")
    if result.configuration_digest != configuration.configuration_digest:
        raise ValueError("selection result configuration is stale")
    for value in (
        result.selection_id,
        result.image_id,
        result.configuration_digest,
        result.processor_name,
        result.processor_version,
        result.backend_name,
        result.backend_version,
    ):
        primitives._bounded_string(
            "OCR identity field",
            value,
            configuration.max_identity_field_characters,
            nonempty=True,
        )
    if len(result.tokens) > configuration.max_tokens_per_selection:
        raise OCRContractLimitError(
            "token count exceeds max_tokens_per_selection"
        )
    if len(result.lines) > configuration.max_lines_per_selection:
        raise OCRContractLimitError(
            "line count exceeds max_lines_per_selection"
        )
    if len(result.warnings) > configuration.max_warnings_per_selection:
        raise OCRContractLimitError(
            "warning count exceeds max_warnings_per_selection"
        )
    if len({item.token_id for item in result.tokens}) != len(result.tokens):
        raise ValueError("OCR token IDs must be unique")
    if len({item.line_id for item in result.lines}) != len(result.lines):
        raise ValueError("OCR line IDs must be unique")
    warning_ids = tuple(warning.warning_id for warning in result.warnings)
    if len(set(warning_ids)) != len(warning_ids):
        raise ValueError("OCR warning IDs must be unique")
    if tuple(item.order for item in result.tokens) != tuple(
        range(len(result.tokens))
    ):
        raise ValueError("OCR token order must be contiguous and ordered")
    if tuple(item.order for item in result.lines) != tuple(
        range(len(result.lines))
    ):
        raise ValueError("OCR line order must be contiguous and ordered")

    text_characters = 0
    result_identity_strings = (
        result.selection_result_id,
        *(token.token_id for token in result.tokens),
        *(line.line_id for line in result.lines),
        *(warning.warning_id for warning in result.warnings),
    )
    for value in result_identity_strings:
        primitives._bounded_string(
            "OCR result identity field",
            value,
            configuration.max_identity_field_characters,
            nonempty=True,
        )
    for warning in result.warnings:
        if warning.selection_id != selection.selection_id:
            raise ValueError("OCR warning refers to the wrong selection")
        primitives._bounded_string(
            "warning code",
            warning.code,
            configuration.max_identity_field_characters,
            nonempty=True,
        )
        primitives._bounded_string(
            "warning message",
            warning.message,
            configuration.max_warning_message_characters,
            nonempty=True,
        )
        if len(warning.evidence) > configuration.max_warning_evidence_entries:
            raise OCRContractLimitError(
                "warning evidence exceeds max_warning_evidence_entries"
            )
        for key, value in warning.evidence:
            primitives._bounded_string(
                "warning evidence key",
                key,
                configuration.max_identity_field_characters,
                nonempty=True,
            )
            primitives._bounded_string(
                "warning evidence value",
                value,
                configuration.max_warning_message_characters,
            )
    for token in result.tokens:
        _validate_output_against_selection(
            token, result, selection, configuration, warning_ids
        )
        text_characters += len(token.text)
    for line in result.lines:
        _validate_output_against_selection(
            line, result, selection, configuration, warning_ids
        )
        text_characters += len(line.text)
    if text_characters > configuration.max_text_characters_per_selection:
        raise OCRContractLimitError(
            "text length exceeds max_text_characters_per_selection"
        )

    mode = configuration.output_mode
    if result.status is OCRSelectionStatus.COMPLETED:
        if result.failure is not None:
            raise ValueError("completed OCR selection cannot have a failure")
        needs_tokens = mode in (
            OCROutputMode.TOKENS,
            OCROutputMode.TOKENS_AND_LINES,
        )
        needs_lines = mode in (
            OCROutputMode.LINES,
            OCROutputMode.TOKENS_AND_LINES,
        )
        has_output = bool(result.tokens or result.lines)
        if has_output and needs_tokens and not result.tokens:
            raise ValueError(
                "completed OCR selection is missing token evidence"
            )
        if has_output and needs_lines and not result.lines:
            raise ValueError("completed OCR selection is missing line evidence")
    elif result.status is OCRSelectionStatus.PARTIAL:
        if result.failure is None or not result.warnings:
            raise ValueError(
                "partial OCR selection requires failure and warning evidence"
            )
        if not result.tokens and not result.lines:
            raise ValueError("partial OCR selection requires usable output")
    else:
        if result.tokens or result.lines:
            raise ValueError("failed OCR selection cannot contain output")
        if result.failure is None or not result.warnings:
            raise ValueError(
                "failed OCR selection requires failure and warning evidence"
            )
    if result.failure is not None:
        if result.failure.selection_id != selection.selection_id:
            raise ValueError("OCR failure refers to the wrong selection")
        primitives._bounded_string(
            "OCR failure ID",
            result.failure.failure_id,
            configuration.max_identity_field_characters,
            nonempty=True,
        )
        primitives._bounded_string(
            "OCR failure message",
            result.failure.message,
            configuration.max_warning_message_characters,
            nonempty=True,
        )
        if not set(result.failure.warning_ids).issubset(warning_ids):
            raise ValueError("OCR failure warning links are unresolved")

    if mode is OCROutputMode.TOKENS:
        if result.lines:
            raise ValueError("token-only OCR result cannot contain lines")
        if any(token.line_order is not None for token in result.tokens):
            raise ValueError(
                "token-only OCR output cannot claim line membership"
            )
    elif mode is OCROutputMode.LINES:
        if result.tokens:
            raise ValueError("line-only OCR result cannot contain tokens")
        if any(line.token_ids for line in result.lines):
            raise ValueError("line-only OCR output cannot link absent tokens")
    elif result.tokens and result.lines:
        token_by_id = {token.token_id: token for token in result.tokens}
        memberships = tuple(
            token_id for line in result.lines for token_id in line.token_ids
        )
        if len(set(memberships)) != len(memberships):
            raise ValueError("OCR tokens must belong to at most one line")
        if set(memberships) != set(token_by_id):
            raise ValueError("token and line membership must be complete")
        for line in result.lines:
            for token_id in line.token_ids:
                token = token_by_id[token_id]
                if token.line_order != line.order:
                    raise ValueError("token line membership is contradictory")
                if not primitives._box_contains(
                    line.pixel_bounding_box, token.pixel_bounding_box
                ):
                    raise ValueError("OCR line must contain its token boxes")


def _validate_output_against_selection(
    output: OCRTextOutput,
    result: OCRSelectionResult,
    selection: OCRSelection,
    configuration: OCRConfiguration,
    warning_ids: tuple[str, ...],
) -> None:

    if output.selection_id != selection.selection_id:
        raise ValueError("OCR output refers to the wrong selection")
    if output.image_id != selection.image.image_id:
        raise ValueError("OCR output refers to the wrong image")
    if output.source_coordinate_system != (
        selection.image.rendered_region.coordinate_system
    ):
        raise ValueError("OCR output source coordinate system is stale")
    if output.configuration_digest != configuration.configuration_digest:
        raise ValueError("OCR output configuration is stale")
    primitives._same_processor_identity(result, output)
    for value in (
        output.pixel_coordinate_system,
        output.source_coordinate_system,
        output.configuration_digest,
        output.processor_name,
        output.processor_version,
        output.backend_name,
        output.backend_version,
        *output.warning_ids,
    ):
        primitives._bounded_string(
            "OCR output identity field",
            value,
            configuration.max_identity_field_characters,
            nonempty=True,
        )
    primitives._bounded_string(
        "OCR output text",
        output.text,
        configuration.max_text_characters_per_item,
        nonempty=True,
    )
    if not set(output.warning_ids).issubset(warning_ids):
        raise ValueError("OCR output warning links are unresolved")
    expected_pixel = geometry._pixel_box(
        selection.image, output.pixel_bounding_box
    )
    if output.pixel_bounding_box != expected_pixel:
        raise ValueError("OCR pixel box is not canonical")
    expected_source = geometry._map_pixel_box(selection.image, expected_pixel)
    if output.source_bounding_box != expected_source:
        raise ValueError("OCR source box does not match pixel mapping")


def _overall_status(
    selection_results: tuple[OCRSelectionResult, ...],
) -> OCRResultStatus:
    from projectkoios.ingestion.ocr.result_status import OCRResultStatus
    from projectkoios.ingestion.ocr.selection_status import OCRSelectionStatus

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

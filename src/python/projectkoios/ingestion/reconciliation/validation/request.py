"""Cross-object reconciliation request validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import (
    ExtractedPage,
)
from projectkoios.ingestion.ocr.result.ocr import OCRResult
from projectkoios.ingestion.reconciliation.limit.error import (
    OCRReconciliationLimitError,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.reconciliation.configuration import (
        OCRReconciliationConfiguration,
    )
from projectkoios.ingestion.reconciliation.validation import value as primitives


def _validate_input_parts(
    ocr_result: OCRResult,
    selection_index: int,
    native_page: ExtractedPage | None,
    layout_result: PageLayoutResult | None,
    configuration: OCRReconciliationConfiguration,
) -> None:
    from projectkoios.ingestion.reconciliation.configuration import (
        OCRReconciliationConfiguration,
    )

    if not isinstance(ocr_result, OCRResult):
        raise TypeError("ocr_result must be OCRResult")
    primitives._nonnegative_integer("selection_index", selection_index)
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
        primitives._bounded_text(
            "native block text",
            block.text,
            limit=configuration.max_text_characters_per_item,
        )
        total_text += len(block.text)
        if total_text > configuration.max_total_text_characters:
            raise OCRReconciliationLimitError(
                "native text exceeds max_total_text_characters"
            )

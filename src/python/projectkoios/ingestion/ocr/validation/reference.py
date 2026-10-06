"""Native-text reference validation for OCR selections."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedPage,
)
from projectkoios.ingestion.ocr.limit.definition import (
    _MAX_NATIVE_PAGE_BLOCKS,
    _MAX_NATIVE_PAGE_SOURCE_SPANS,
)
from projectkoios.ingestion.ocr.limit.error import OCRContractLimitError

if TYPE_CHECKING:
    from projectkoios.ingestion.ocr.image.page import OCRPageImage
    from projectkoios.ingestion.ocr.reference.native.text.block import (
        OCRNativeTextBlockReference,
    )
from projectkoios.ingestion.ocr.validation import value as primitives


def _native_text_references(
    image: OCRPageImage,
    page: ExtractedPage,
    block_ids: tuple[str, ...],
) -> tuple[OCRNativeTextBlockReference, ...]:
    from projectkoios.ingestion.ocr.reference.native.text.block import (
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

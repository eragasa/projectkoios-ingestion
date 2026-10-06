"""Article-structure validation input."""

from __future__ import annotations

from projectkoios.ingestion.articles.structure.configuration import (
    ArticleStructureConfiguration,
)
from projectkoios.ingestion.articles.structure.limits.error import (
    ArticleStructureLimitError,
)
from projectkoios.ingestion.layout import (
    PageLayoutResult,
)
from projectkoios.ingestion.models import (
    ExtractedDocument,
)


def _validate_input(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    configuration: ArticleStructureConfiguration,
) -> None:
    if not isinstance(document, ExtractedDocument):
        raise TypeError("document must be ExtractedDocument")
    if not isinstance(layouts, tuple):
        raise TypeError("layouts must be an immutable tuple")
    if len(document.pages) > configuration.max_pages:
        raise ArticleStructureLimitError("document pages exceed max_pages")
    if len(layouts) != len(document.pages):
        raise ValueError("one layout result is required per document page")
    if any(not isinstance(layout, PageLayoutResult) for layout in layouts):
        raise TypeError("layouts must contain PageLayoutResult values")
    total_input_blocks = 0
    input_block_ids: set[str] = set()
    total_blocks = 0
    total_text = 0
    for page, layout in zip(document.pages, layouts, strict=True):
        if (
            layout.source_id != document.source.source_id
            or layout.source_blob_id != document.source.blob_id
            or layout.source_content_hash != document.source.content_hash
            or layout.page_index != page.page_index
            or layout.page_width != page.width
            or layout.page_height != page.height
            or layout.coordinate_system != page.coordinate_system
            or layout.rotation_degrees != page.rotation_degrees
        ):
            raise ValueError("layout result does not match its document page")
        expected_raw = tuple(
            (block.block_id, block.kind, block.source_spans)
            for block in page.blocks
        )
        actual_raw = tuple(
            (item.block_id, item.kind, item.source_spans)
            for item in layout.raw_blocks
        )
        if expected_raw != actual_raw:
            raise ValueError("layout raw blocks do not match the document page")
        total_input_blocks += len(page.blocks)
        for block in page.blocks:
            if block.block_id in input_block_ids:
                raise ValueError("document block IDs must be globally unique")
            input_block_ids.add(block.block_id)
        if total_input_blocks > configuration.max_input_blocks:
            raise ArticleStructureLimitError(
                "input blocks exceed max_input_blocks"
            )
        for block in page.blocks:
            if block.kind == "text" and isinstance(block.text, str):
                total_blocks += 1
                total_text += len(block.text)
                if total_blocks > configuration.max_text_blocks:
                    raise ArticleStructureLimitError(
                        "text blocks exceed max_text_blocks"
                    )
                if total_text > configuration.max_text_characters:
                    raise ArticleStructureLimitError(
                        "text exceeds max_text_characters"
                    )

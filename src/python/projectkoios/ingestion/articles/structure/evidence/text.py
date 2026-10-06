"""Article-structure evidence text."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.articles.structure.configuration import (
    ArticleStructureConfiguration,
)
from projectkoios.ingestion.articles.structure.limits.error import (
    ArticleStructureLimitError,
)
from projectkoios.ingestion.articles.structure.normalization.text import (
    _normalized_text,
)
from projectkoios.ingestion.layout import (
    PageLayoutResult,
)
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedBlock,
    ExtractedDocument,
)


@dataclass(frozen=True)
class _TextEvidence:
    block: ExtractedBlock
    page_index: int
    page_height: float
    source_key: tuple[int, int, int]
    reading_confidence: float

    @property
    def text(self) -> str:
        assert self.block.text is not None
        return self.block.text

    @property
    def normalized_text(self) -> str:
        return _normalized_text(self.text)

    @property
    def bounding_box(self) -> BoundingBox | None:
        boxes = tuple(
            span.bounding_box
            for span in self.block.source_spans
            if span.bounding_box is not None
        )
        if len(boxes) != len(self.block.source_spans) or not boxes:
            return None
        return (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )


def _ordered_text_evidence(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    configuration: ArticleStructureConfiguration,
) -> tuple[_TextEvidence, ...]:
    evidence: list[_TextEvidence] = []
    for page_order, (page, layout) in enumerate(
        zip(document.pages, layouts, strict=True)
    ):
        blocks = {block.block_id: block for block in page.blocks}
        raw_order = {
            block.block_id: index for index, block in enumerate(page.blocks)
        }
        proposed = set(layout.proposed_order)
        ordered_ids = list(layout.proposed_order)
        ordered_ids.extend(
            block.block_id
            for block in page.blocks
            if block.kind == "text" and block.block_id not in proposed
        )
        for local_order, block_id in enumerate(ordered_ids):
            block = blocks[block_id]
            if not isinstance(block.text, str) or not block.text.strip():
                continue
            if len(block.text) > configuration.max_text_characters:
                raise ArticleStructureLimitError(
                    "text block exceeds max_text_characters"
                )
            reading_confidence = min(
                block.confidence,
                layout.confidence if block_id in proposed else 0.35,
            )
            evidence.append(
                _TextEvidence(
                    block=block,
                    page_index=page.page_index,
                    page_height=page.height,
                    source_key=(
                        page_order,
                        local_order,
                        raw_order[block_id],
                    ),
                    reading_confidence=reading_confidence,
                )
            )
    return tuple(evidence)

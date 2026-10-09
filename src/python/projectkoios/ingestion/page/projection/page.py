"""Citation-aligned output pages and pure page derivation."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.page.projection.block import (
    PageProjectionTextBlock,
    PageProjectionTextBlockInventory,
    PageProjectionTextBlockStyle,
)
from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.identity import (
    PageProjectionResultIdentityDerivation,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)
from projectkoios.ingestion.page.projection.limits.error import (
    PageProjectionLimitError,
)
from projectkoios.ingestion.transcript.reading.evidence.block.equation.evidence import (  # noqa: E501
    ReadingEquationEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.figure.evidence import (  # noqa: E501
    ReadingFigureEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.kind import (
    ReadingEvidenceBlockKind,
)
from projectkoios.ingestion.transcript.reading.evidence.block.table.evidence import (  # noqa: E501
    ReadingTableEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.evidence import (  # noqa: E501
    ReadingTextEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.caption.evidence import (  # noqa: E501
    ReadingCaptionEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.document.definition import (  # noqa: E501
    ReadingEvidenceDocument,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)


def normalize_page_projection_collision_text(value: str) -> str:
    """Return NFC whitespace-compacted text for collision checks only."""
    return unicodedata.normalize("NFC", " ".join(value.split()))


@dataclass(frozen=True, slots=True)
class PageProjectionPage:
    """Bind one complete citation location to its text-only projection."""

    source_page_id: ReadingEvidenceIdentity
    page_location: ReadingPageLocation
    blocks: PageProjectionTextBlockInventory
    page_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.source_page_id) is not ReadingEvidenceIdentity or (
            self.source_page_id.kind
            is not ReadingEvidenceIdentityKind.EVIDENCE_PAGE
        ):
            raise TypeError("source_page_id has the wrong identity role")
        if type(self.page_location) is not ReadingPageLocation:
            raise TypeError("page_location must be ReadingPageLocation")
        if type(self.blocks) is not PageProjectionTextBlockInventory:
            raise TypeError("blocks must be PageProjectionTextBlockInventory")
        object.__setattr__(
            self,
            "page_id",
            PageProjectionResultIdentityDerivation.derive_page(
                source_page_id=self.source_page_id.value,
                location_id=self.page_location.location_id.value,
                block_inventory_id=self.blocks.inventory_id,
            ),
        )

    @property
    def physical_page_index(self) -> int:
        """Return the zero-based physical citation index."""
        return self.page_location.physical_page_index

    @property
    def physical_page_number(self) -> int:
        """Return the positive physical citation number."""
        return self.page_location.physical_page_number

    @property
    def printed_page_label(self) -> str | None:
        """Return the optional exact printed citation label."""
        return self.page_location.printed_page_label


@dataclass(frozen=True, slots=True, init=False)
class PageProjectionPageInventory:
    """Own a contiguous physical-page-ordered projection inventory."""

    _pages: tuple[PageProjectionPage, ...] = field(repr=True)
    block_count: int
    projected_text_bytes: int
    inventory_id: str = field(init=False)

    def __init__(self, *pages: PageProjectionPage) -> None:
        values = tuple(pages)
        if not values:
            raise PageProjectionError(
                "projected page inventory must not be empty"
            )
        PAGE_PROJECTION_LIMITS.require_count(
            len(values),
            "projected page count",
            maximum=PAGE_PROJECTION_LIMITS.maximum_pages,
        )
        if any(type(value) is not PageProjectionPage for value in values):
            raise TypeError("page inventory requires exact projected pages")
        indexes = tuple(value.physical_page_index for value in values)
        expected_indexes = tuple(range(indexes[0], indexes[0] + len(values)))
        if indexes != expected_indexes:
            raise PageProjectionError(
                "projected pages must be physically contiguous and ordered"
            )
        source_page_ids = tuple(value.source_page_id.value for value in values)
        if len(source_page_ids) != len(set(source_page_ids)):
            raise PageProjectionError(
                "projected source page identities must be unique"
            )
        block_count = sum(len(value.blocks) for value in values)
        PAGE_PROJECTION_LIMITS.require_count(
            block_count,
            "projected block count",
            maximum=PAGE_PROJECTION_LIMITS.maximum_blocks,
        )
        projected_text_bytes = sum(
            value.blocks.projected_text_bytes for value in values
        )
        if (
            projected_text_bytes
            > PAGE_PROJECTION_LIMITS.maximum_projected_text_bytes
        ):
            raise PageProjectionLimitError(
                "projected document text exceeds its limit"
            )
        object.__setattr__(self, "_pages", values)
        object.__setattr__(self, "block_count", block_count)
        object.__setattr__(self, "projected_text_bytes", projected_text_bytes)
        object.__setattr__(
            self,
            "inventory_id",
            PageProjectionResultIdentityDerivation.derive_page_inventory(
                page_ids=tuple(value.page_id for value in values)
            ),
        )

    def __iter__(self) -> Iterator[PageProjectionPage]:
        return iter(self._pages)

    def __len__(self) -> int:
        return len(self._pages)


def derive_page_projection_pages(
    *,
    document: ReadingEvidenceDocument,
    include_figure_captions: bool,
) -> PageProjectionPageInventory:
    """Project mandatory text and configured captions without side effects."""
    if type(document) is not ReadingEvidenceDocument:
        raise TypeError("document must be ReadingEvidenceDocument")
    if type(include_figure_captions) is not bool:
        raise TypeError("include_figure_captions must be an exact bool")
    source_pages = tuple(document.pages)
    source_blocks = tuple(
        block for page in source_pages for block in page.blocks
    )
    work_count = len(source_pages) + len(source_blocks)
    PAGE_PROJECTION_LIMITS.require_count(
        work_count,
        "page projection work",
        maximum=PAGE_PROJECTION_LIMITS.maximum_total_work,
    )
    normalized_text = {
        normalize_page_projection_collision_text(block.text)
        for block in source_blocks
        if type(block) is ReadingTextEvidenceBlock
    }
    observed_caption_ids: set[str] = set()
    observed_caption_text: set[str] = set()
    projected_pages: list[PageProjectionPage] = []
    for source_page in source_pages:
        projected_blocks: list[PageProjectionTextBlock] = []
        for source_block in source_page.blocks:
            if type(source_block) is ReadingTextEvidenceBlock:
                style = (
                    PageProjectionTextBlockStyle.PARAGRAPH
                    if source_block.kind is ReadingEvidenceBlockKind.PARAGRAPH
                    else PageProjectionTextBlockStyle.HEADING
                )
                projected_blocks.append(
                    PageProjectionTextBlock(
                        order_index=source_block.order_index,
                        text=source_block.text,
                        style=style,
                        source_id=source_block.block_id,
                    )
                )
                continue
            if type(source_block) is ReadingFigureEvidenceBlock:
                caption = source_block.caption
                if include_figure_captions and caption is not None:
                    if type(caption) is not ReadingCaptionEvidence:
                        raise PageProjectionError(
                            "figure caption has an unsupported type"
                        )
                    caption_id = caption.caption_id.value
                    normalized_caption = (
                        normalize_page_projection_collision_text(caption.text)
                    )
                    if caption_id in observed_caption_ids:
                        raise PageProjectionError(
                            "figure caption identity is duplicated"
                        )
                    if normalized_caption in normalized_text or (
                        normalized_caption in observed_caption_text
                    ):
                        raise PageProjectionError(
                            "figure caption duplicates projected text"
                        )
                    observed_caption_ids.add(caption_id)
                    observed_caption_text.add(normalized_caption)
                    projected_blocks.append(
                        PageProjectionTextBlock(
                            order_index=source_block.order_index,
                            text=caption.text,
                            style=(PageProjectionTextBlockStyle.FIGURE_CAPTION),
                            source_id=caption.caption_id,
                        )
                    )
                continue
            if type(source_block) in (
                ReadingTableEvidenceBlock,
                ReadingEquationEvidenceBlock,
            ):
                continue
            raise PageProjectionError(
                "canonical reading block has an unsupported type"
            )
        projected_pages.append(
            PageProjectionPage(
                source_page_id=source_page.page_id,
                page_location=source_page.page_location,
                blocks=PageProjectionTextBlockInventory(*projected_blocks),
            )
        )
    return PageProjectionPageInventory(*projected_pages)

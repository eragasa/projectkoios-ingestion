"""Immutable semantic text blocks for page projection."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

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
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)


class PageProjectionTextBlockStyle(StrEnum):
    """Define the complete output text-style grammar."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    FIGURE_CAPTION = "figure_caption"


@dataclass(frozen=True, slots=True)
class PageProjectionTextBlock:
    """Bind exact projected text to order, style, and source evidence."""

    order_index: int
    text: str
    style: PageProjectionTextBlockStyle
    source_id: ReadingEvidenceIdentity
    block_id: str = field(init=False)

    def __post_init__(self) -> None:
        PAGE_PROJECTION_LIMITS.require_count(
            self.order_index,
            "order_index",
            maximum=PAGE_PROJECTION_LIMITS.maximum_blocks,
        )
        text = PAGE_PROJECTION_LIMITS.require_text(
            self.text,
            "projected block text",
            maximum_bytes=PAGE_PROJECTION_LIMITS.maximum_block_text_bytes,
        )
        if not isinstance(self.style, PageProjectionTextBlockStyle):
            raise TypeError("style must be PageProjectionTextBlockStyle")
        if type(self.source_id) is not ReadingEvidenceIdentity or (
            self.source_id.kind
            not in (
                ReadingEvidenceIdentityKind.BLOCK,
                ReadingEvidenceIdentityKind.CAPTION,
            )
        ):
            raise TypeError("source_id has an unsupported identity role")
        if (
            self.style is PageProjectionTextBlockStyle.FIGURE_CAPTION
            and self.source_id.kind is not ReadingEvidenceIdentityKind.CAPTION
        ) or (
            self.style is not PageProjectionTextBlockStyle.FIGURE_CAPTION
            and self.source_id.kind is not ReadingEvidenceIdentityKind.BLOCK
        ):
            raise PageProjectionError(
                "projected block style differs from its source identity"
            )
        object.__setattr__(
            self,
            "block_id",
            PageProjectionResultIdentityDerivation.derive_block(
                order_index=self.order_index,
                text=text,
                style=self.style.value,
                source_id=self.source_id.value,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class PageProjectionTextBlockInventory:
    """Own ordered projected blocks with unique order and source identity."""

    _blocks: tuple[PageProjectionTextBlock, ...] = field(repr=True)
    projected_text_bytes: int
    inventory_id: str = field(init=False)

    def __init__(self, *blocks: PageProjectionTextBlock) -> None:
        values = tuple(blocks)
        PAGE_PROJECTION_LIMITS.require_count(
            len(values),
            "projected page block count",
            maximum=PAGE_PROJECTION_LIMITS.maximum_page_blocks,
        )
        if any(type(value) is not PageProjectionTextBlock for value in values):
            raise TypeError("block inventory requires exact projected blocks")
        orders = tuple(value.order_index for value in values)
        if orders != tuple(sorted(orders)) or len(orders) != len(set(orders)):
            raise PageProjectionError(
                "projected block order must be increasing and unique"
            )
        source_ids = tuple(value.source_id.value for value in values)
        if len(source_ids) != len(set(source_ids)):
            raise PageProjectionError(
                "projected block source identities must be unique"
            )
        projected_text_bytes = sum(
            len(value.text.encode("utf-8", errors="strict")) for value in values
        )
        if (
            projected_text_bytes
            > PAGE_PROJECTION_LIMITS.maximum_projected_text_bytes
        ):
            raise PageProjectionLimitError(
                "projected page text exceeds its limit"
            )
        object.__setattr__(self, "_blocks", values)
        object.__setattr__(self, "projected_text_bytes", projected_text_bytes)
        object.__setattr__(
            self,
            "inventory_id",
            PageProjectionResultIdentityDerivation.derive_block_inventory(
                block_ids=tuple(value.block_id for value in values)
            ),
        )

    def __bool__(self) -> bool:
        return bool(self._blocks)

    def __iter__(self) -> Iterator[PageProjectionTextBlock]:
        return iter(self._blocks)

    def __len__(self) -> int:
        return len(self._blocks)

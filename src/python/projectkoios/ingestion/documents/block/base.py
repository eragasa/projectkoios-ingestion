"""Nominal base for document blocks."""

from __future__ import annotations

from abc import ABC, abstractmethod


class AbstractDocumentBlock(ABC):
    """Nominal base shared by concrete document blocks."""

    __slots__ = ()

    page_index: int
    printed_page_label: str | None
    order_index: int

    @property
    @abstractmethod
    def document_block_id(self) -> str:
        """Return the concrete document block's stable identity."""

    @property
    @abstractmethod
    def document_text(self) -> str:
        """Return the concrete document block's canonical text."""


__all__ = ["AbstractDocumentBlock"]

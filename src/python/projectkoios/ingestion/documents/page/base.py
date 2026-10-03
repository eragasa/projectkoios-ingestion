"""Nominal base for document pages."""

from __future__ import annotations

from abc import ABC, abstractmethod


class AbstractDocumentPage(ABC):
    """Nominal base shared by concrete document pages."""

    __slots__ = ()

    page_index: int
    printed_page_label: str | None

    @property
    @abstractmethod
    def document_page_id(self) -> str:
        """Return the concrete document page's stable identity."""

    @property
    @abstractmethod
    def document_block_ids(self) -> tuple[str, ...]:
        """Return block identities in canonical page order."""

    @property
    @abstractmethod
    def document_text(self) -> str:
        """Return the concrete document page's canonical text."""


__all__ = ["AbstractDocumentPage"]

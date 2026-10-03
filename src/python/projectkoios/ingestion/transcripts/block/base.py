"""Nominal base for transcript blocks."""

from __future__ import annotations

from abc import abstractmethod

from projectkoios.ingestion.documents.block.base import AbstractDocumentBlock


class AbstractTranscriptBlock(AbstractDocumentBlock):
    """Nominal base shared by concrete transcript blocks."""

    __slots__ = ()

    page_index: int
    printed_page_label: str | None
    order_index: int

    @property
    def document_block_id(self) -> str:
        return self.transcript_block_id

    @property
    def document_text(self) -> str:
        return self.transcript_text

    @property
    @abstractmethod
    def transcript_block_id(self) -> str:
        """Return the concrete transcript block's stable identity."""

    @property
    @abstractmethod
    def transcript_text(self) -> str:
        """Return the concrete block's canonical text projection."""


__all__ = ["AbstractTranscriptBlock"]

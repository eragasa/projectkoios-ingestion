"""Nominal base for transcript pages."""

from __future__ import annotations

from abc import abstractmethod

from projectkoios.ingestion.documents.page.base import AbstractDocumentPage


class AbstractTranscriptPage(AbstractDocumentPage):
    """Nominal base shared by concrete transcript pages."""

    __slots__ = ()

    page_index: int
    printed_page_label: str | None

    @property
    def document_page_id(self) -> str:
        return self.transcript_page_id

    @property
    def document_block_ids(self) -> tuple[str, ...]:
        return self.transcript_block_ids

    @property
    def document_text(self) -> str:
        return self.transcript_text

    @property
    @abstractmethod
    def transcript_page_id(self) -> str:
        """Return the concrete transcript page's stable identity."""

    @property
    @abstractmethod
    def transcript_block_ids(self) -> tuple[str, ...]:
        """Return block identities in canonical page order."""

    @property
    @abstractmethod
    def transcript_text(self) -> str:
        """Return the concrete page's canonical text projection."""


__all__ = ["AbstractTranscriptPage"]

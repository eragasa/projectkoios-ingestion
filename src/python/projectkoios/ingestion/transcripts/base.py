"""Nominal base for transcript aggregates."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from projectkoios.ingestion.documents.base import AbstractDocument

if TYPE_CHECKING:
    from projectkoios.ingestion.transcripts.block.base import (
        AbstractTranscriptBlock,
    )
    from projectkoios.ingestion.transcripts.page.base import (
        AbstractTranscriptPage,
    )


class AbstractTranscript(AbstractDocument):
    """Nominal base shared by concrete transcript aggregates."""

    __slots__ = ()

    @property
    @abstractmethod
    def transcript_id(self) -> str:
        """Return the concrete transcript's stable identity."""

    @property
    @abstractmethod
    def transcript_pages(self) -> tuple[AbstractTranscriptPage, ...]:
        """Return pages in canonical transcript order."""

    @property
    @abstractmethod
    def transcript_blocks(self) -> tuple[AbstractTranscriptBlock, ...]:
        """Return blocks in canonical transcript order."""

    @property
    @abstractmethod
    def transcript_text(self) -> str:
        """Return the concrete transcript's canonical text projection."""


__all__ = ["AbstractTranscript"]

"""Nominal chunk-index publication boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from projectkoios.chunking import TextChunk


class ChunkIndexWriter(ABC):
    """Write exact text chunks to an external index implementation."""

    __slots__ = ()

    @abstractmethod
    def add_chunks(self, chunks: Iterable[TextChunk]) -> None:
        """Add the supplied chunks to the owned index."""

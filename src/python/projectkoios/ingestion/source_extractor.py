"""Nominal source-extraction boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO

from projectkoios.ingestion.models import ExtractionResult, SourceDocument


class SourceExtractor(ABC):
    """Extract one exact source through a concrete ingestion adapter."""

    __slots__ = ()

    name: str
    version: str

    @abstractmethod
    def extract(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractionResult:
        """Extract the supplied source bytes without changing them."""

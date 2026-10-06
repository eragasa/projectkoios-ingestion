"""Nominal document-structure analyzer boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.models import ExtractedDocument
from projectkoios.ingestion.structure import StructureAnalysis


class DocumentStructureAnalyzer(ABC):
    """Analyze extracted-document structure through an implementation."""

    __slots__ = ()

    @abstractmethod
    def analyze(self, document: ExtractedDocument) -> StructureAnalysis:
        """Propose source-backed structure for one extracted document."""

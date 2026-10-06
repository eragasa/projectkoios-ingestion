"""Nominal table-structure reconstruction boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.tables.contracts import TableDetectionResult
from projectkoios.ingestion.tables.structure.result import TableStructureResult


class TableStructureReconstructor(ABC):
    """Propose table structure without accepting or proofreading it."""

    __slots__ = ()

    name: str
    version: str

    @abstractmethod
    def reconstruct(
        self, detection_result: TableDetectionResult
    ) -> TableStructureResult:
        """Reconstruct proposed structure from one detection result."""

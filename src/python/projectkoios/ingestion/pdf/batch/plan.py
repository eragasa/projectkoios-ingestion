"""Immutable ordered PDF batch plan."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.pdf.batch.item import PdfBatchItem
from projectkoios.ingestion.pdf.batch.limits.definition import (
    MAX_PDF_BATCH_ITEMS,
)
from projectkoios.ingestion.pdf.batch.limits.error import PdfBatchLimitError


@dataclass(frozen=True, slots=True)
class PdfBatchPlan:
    """Hold one bounded ordered collection of PDF source declarations."""

    schema_version: int
    items: tuple[PdfBatchItem, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported PDF batch-plan schema version")
        if not isinstance(self.items, tuple) or not self.items:
            raise ValueError("PDF batch plan must contain an item tuple")
        if any(not isinstance(item, PdfBatchItem) for item in self.items):
            raise ValueError("PDF batch plan items must be PdfBatchItem values")
        if len(self.items) > MAX_PDF_BATCH_ITEMS:
            raise PdfBatchLimitError("PDF batch plan exceeds the item limit")
        self._require_unique(
            "source_id", tuple(item.source_id for item in self.items)
        )
        self._require_unique(
            "pdf_path", tuple(item.pdf_path.as_posix() for item in self.items)
        )
        self._require_unique(
            "output_directory",
            tuple(item.output_directory.as_posix() for item in self.items),
        )

    @staticmethod
    def _require_unique(field: str, values: tuple[str, ...]) -> None:
        if len(values) != len(set(values)):
            raise ValueError(
                f"PDF batch plan contains duplicate {field} values"
            )

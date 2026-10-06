"""_Candidate reconciliation domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.reconciliation.kind.match import (
    OCRReconciliationMatchKind,
)


@dataclass(frozen=True)
class _Candidate:
    native_segment_id: str
    ocr_line_id: str
    kind: OCRReconciliationMatchKind
    text_similarity: float
    geometry_overlap: float | None
    score: float
    native_order: int
    ocr_order: int

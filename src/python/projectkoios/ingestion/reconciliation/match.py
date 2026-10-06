"""OCRReconciliationMatch reconciliation domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.reconciliation.geometry import analysis as geometry
from projectkoios.ingestion.reconciliation.identity import (
    derivation as identity,
)
from projectkoios.ingestion.reconciliation.kind.match import (
    OCRReconciliationMatchKind,
)
from projectkoios.ingestion.reconciliation.validation import value as primitives


@dataclass(frozen=True)
class OCRReconciliationMatch(AbstractImmutableDataObject):
    match_id: str
    kind: OCRReconciliationMatchKind
    native_segment_id: str
    ocr_line_id: str
    text_similarity: float
    geometry_overlap: float | None
    warning_ids: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        kind: OCRReconciliationMatchKind,
        native_segment_id: str,
        ocr_line_id: str,
        text_similarity: float,
        geometry_overlap: float | None,
        warning_ids: tuple[str, ...] = (),
    ) -> OCRReconciliationMatch:
        if not isinstance(kind, OCRReconciliationMatchKind):
            raise ValueError("reconciliation match kind is unsupported")
        primitives._bounded_string("native segment ID", native_segment_id)
        primitives._bounded_string("OCR line ID", ocr_line_id)
        primitives._require_unique_strings("match warning IDs", warning_ids)
        similarity = geometry._unit_float("text_similarity", text_similarity)
        overlap = (
            geometry._unit_float("geometry_overlap", geometry_overlap)
            if geometry_overlap is not None
            else None
        )
        match_id = identity._match_id(
            kind,
            native_segment_id,
            ocr_line_id,
            similarity,
            overlap,
            warning_ids,
        )
        return cls(
            match_id=match_id,
            kind=kind,
            native_segment_id=native_segment_id,
            ocr_line_id=ocr_line_id,
            text_similarity=similarity,
            geometry_overlap=overlap,
            warning_ids=warning_ids,
        )

    def __post_init__(self) -> None:
        primitives._bounded_string("match ID", self.match_id)
        if not isinstance(self.kind, OCRReconciliationMatchKind):
            raise ValueError("reconciliation match kind is unsupported")
        primitives._bounded_string("native segment ID", self.native_segment_id)
        primitives._bounded_string("OCR line ID", self.ocr_line_id)
        object.__setattr__(
            self,
            "text_similarity",
            geometry._unit_float("text_similarity", self.text_similarity),
        )
        if self.geometry_overlap is not None:
            object.__setattr__(
                self,
                "geometry_overlap",
                geometry._unit_float("geometry_overlap", self.geometry_overlap),
            )
        primitives._require_unique_strings(
            "match warning IDs", self.warning_ids
        )
        if self.kind is OCRReconciliationMatchKind.DUPLICATE:
            if self.text_similarity != 1.0 or self.warning_ids:
                raise ValueError(
                    "duplicate matches require exact text and no warning"
                )
        elif not self.warning_ids:
            raise ValueError("disagreement matches require warning evidence")
        expected = identity._match_id(
            self.kind,
            self.native_segment_id,
            self.ocr_line_id,
            self.text_similarity,
            self.geometry_overlap,
            self.warning_ids,
        )
        if self.match_id != expected:
            raise ValueError("reconciliation match ID is inconsistent")

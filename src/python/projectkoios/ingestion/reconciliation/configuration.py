"""OCRReconciliationConfiguration reconciliation domain object."""

from __future__ import annotations

import math
from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.reconciliation import _primitives as primitives
from projectkoios.ingestion.reconciliation._limits import (
    _MAX_CANDIDATE_PAIRS,
    _MAX_COMPARISON_TEXT_CHARACTERS,
    _MAX_COMPARISON_WORK,
    _MAX_NATIVE_BLOCKS,
    _MAX_NATIVE_SEGMENTS,
    _MAX_OCR_LINES,
    _MAX_RESULT_BYTES,
    _MAX_TEXT_CHARACTERS_PER_ITEM,
    _MAX_TOTAL_TEXT_CHARACTERS,
    _MAX_WARNINGS,
)
from projectkoios.ingestion.reconciliation.limit_error import (
    OCRReconciliationLimitError,
)


@dataclass(frozen=True)
class OCRReconciliationConfiguration(AbstractImmutableDataObject):
    """Deterministic matching thresholds and hard processing limits."""

    minimum_geometry_overlap: float = 0.5
    minimum_disagreement_similarity: float = 0.5
    ambiguity_score_delta: float = 0.02
    max_native_blocks: int = _MAX_NATIVE_BLOCKS
    max_native_segments: int = _MAX_NATIVE_SEGMENTS
    max_ocr_lines: int = _MAX_OCR_LINES
    max_candidate_pairs: int = _MAX_CANDIDATE_PAIRS
    max_comparison_work: int = _MAX_COMPARISON_WORK
    max_comparison_text_characters: int = _MAX_COMPARISON_TEXT_CHARACTERS
    max_text_characters_per_item: int = _MAX_TEXT_CHARACTERS_PER_ITEM
    max_total_text_characters: int = _MAX_TOTAL_TEXT_CHARACTERS
    max_warnings: int = _MAX_WARNINGS
    max_result_bytes: int = _MAX_RESULT_BYTES

    def __post_init__(self) -> None:
        for name in (
            "minimum_geometry_overlap",
            "minimum_disagreement_similarity",
            "ambiguity_score_delta",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError(f"{name} must be a finite number")
            normalized = float(value)
            requires_positive = name != "ambiguity_score_delta"
            if (
                not math.isfinite(normalized)
                or normalized > 1.0
                or normalized < 0.0
                or (requires_positive and normalized == 0.0)
            ):
                qualifier = "greater than zero and" if requires_positive else ""
                raise ValueError(
                    f"{name} must be {qualifier} no greater than one"
                )
            object.__setattr__(self, name, normalized)
        for name, hard_maximum in (
            ("max_native_blocks", _MAX_NATIVE_BLOCKS),
            ("max_native_segments", _MAX_NATIVE_SEGMENTS),
            ("max_ocr_lines", _MAX_OCR_LINES),
            ("max_candidate_pairs", _MAX_CANDIDATE_PAIRS),
            ("max_comparison_work", _MAX_COMPARISON_WORK),
            (
                "max_comparison_text_characters",
                _MAX_COMPARISON_TEXT_CHARACTERS,
            ),
            (
                "max_text_characters_per_item",
                _MAX_TEXT_CHARACTERS_PER_ITEM,
            ),
            ("max_total_text_characters", _MAX_TOTAL_TEXT_CHARACTERS),
            ("max_warnings", _MAX_WARNINGS),
            ("max_result_bytes", _MAX_RESULT_BYTES),
        ):
            value = getattr(self, name)
            primitives._positive_integer(name, value)
            if value > hard_maximum:
                raise OCRReconciliationLimitError(
                    f"{name} exceeds the implementation maximum "
                    f"({hard_maximum})"
                )

    @property
    def configuration_digest(self) -> str:
        return stable_id(
            "ocr-reconciliation-configuration", self.identity_parts()
        )

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.minimum_geometry_overlap,
            self.minimum_disagreement_similarity,
            self.ambiguity_score_delta,
            self.max_native_blocks,
            self.max_native_segments,
            self.max_ocr_lines,
            self.max_candidate_pairs,
            self.max_comparison_work,
            self.max_comparison_text_characters,
            self.max_text_characters_per_item,
            self.max_total_text_characters,
            self.max_warnings,
            self.max_result_bytes,
        )

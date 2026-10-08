"""Semantic reference-evidence completeness reasons."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.validation import (
    REFERENCE_EVIDENCE_VALUE_REQUIREMENTS,
)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceCompletenessReasonInventory:
    """Own sorted, unique, bounded completeness-reason text."""

    _reasons: tuple[str, ...] = field(default=(), repr=False)

    def __init__(self, *reasons: str) -> None:
        values = tuple(reasons)
        if len(values) > REFERENCE_EVIDENCE_LIMITS.maximum_limitations:
            raise ValueError(
                "reference-evidence completeness_reasons is too large"
            )
        if tuple(sorted(values)) != values or len(set(values)) != len(values):
            raise ValueError("completeness reasons must be unique and sorted")
        requirements = REFERENCE_EVIDENCE_VALUE_REQUIREMENTS
        for index, reason in enumerate(values):
            requirements.require_text(reason, f"completeness_reasons[{index}]")
        object.__setattr__(self, "_reasons", values)

    def __iter__(self) -> Iterator[str]:
        return iter(self._reasons)

    def __len__(self) -> int:
        return len(self._reasons)

    def __bool__(self) -> bool:
        return bool(self._reasons)


REFERENCE_EVIDENCE_COMPLETE_REASONS = (
    ReferenceEvidenceCompletenessReasonInventory()
)

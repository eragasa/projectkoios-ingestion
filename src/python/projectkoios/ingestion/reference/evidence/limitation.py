"""Semantic reference-evidence limitations."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.validation import (
    REFERENCE_EVIDENCE_VALUE_REQUIREMENTS,
)

REFERENCE_EVIDENCE_REQUIRED_LIMITATIONS = (
    "automated_unreviewed",
    "not_extraction_accuracy_verification",
    "not_human_proofread",
    "not_independent_revalidation",
    "not_producer_authentication",
    "not_publication_suitable",
    "not_scientifically_validated",
    "not_semantically_corrected",
)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceLimitationInventory:
    """Own sorted, unique, bounded evidence limitation text."""

    _limitations: tuple[str, ...] = field(repr=False)

    def __init__(self, *limitations: str) -> None:
        values = tuple(limitations)
        if not values:
            raise ValueError("reference-evidence limitations must be non-empty")
        if len(values) > REFERENCE_EVIDENCE_LIMITS.maximum_limitations:
            raise ValueError("reference-evidence limitations is too large")
        if tuple(sorted(values)) != values or len(set(values)) != len(values):
            raise ValueError(
                "reference-evidence limitations must be unique and sorted"
            )
        requirements = REFERENCE_EVIDENCE_VALUE_REQUIREMENTS
        for index, limitation in enumerate(values):
            requirements.require_text(
                limitation,
                f"reference-evidence limitations[{index}]",
            )
        if not set(REFERENCE_EVIDENCE_REQUIRED_LIMITATIONS).issubset(values):
            raise ValueError("reference-evidence limitations are incomplete")
        object.__setattr__(self, "_limitations", values)

    def __iter__(self) -> Iterator[str]:
        return iter(self._limitations)

    def __len__(self) -> int:
        return len(self._limitations)


REFERENCE_EVIDENCE_LIMITATIONS = ReferenceEvidenceLimitationInventory(
    *REFERENCE_EVIDENCE_REQUIRED_LIMITATIONS
)

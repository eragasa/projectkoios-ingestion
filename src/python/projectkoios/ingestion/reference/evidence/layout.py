"""Semantic transcript layout lineage for reference evidence."""

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
class ReferenceEvidenceLayoutIdentityInventory:
    """Own ordered, unique, bounded layout result identities."""

    _identities: tuple[str, ...] = field(repr=False)

    def __init__(self, *identities: str) -> None:
        values = tuple(identities)
        if not values:
            raise ValueError("transcript layout_result_ids must be non-empty")
        if len(values) > REFERENCE_EVIDENCE_LIMITS.maximum_layout_identities:
            raise ValueError("transcript layout_result_ids is too large")
        if len(set(values)) != len(values):
            raise ValueError("transcript layout_result_ids must be unique")
        requirements = REFERENCE_EVIDENCE_VALUE_REQUIREMENTS
        for index, identity in enumerate(values):
            requirements.require_text(
                identity,
                f"transcript layout_result_ids[{index}]",
            )
        object.__setattr__(self, "_identities", values)

    def __iter__(self) -> Iterator[str]:
        return iter(self._identities)

    def __len__(self) -> int:
        return len(self._identities)

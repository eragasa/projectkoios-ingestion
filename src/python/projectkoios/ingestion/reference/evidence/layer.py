"""Semantic audited-layer counts for reference evidence."""

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
class ReferenceEvidenceLayerCount:
    """Record one normalized audited-layer count."""

    layer: str
    count: int

    def __post_init__(self) -> None:
        requirements = REFERENCE_EVIDENCE_VALUE_REQUIREMENTS
        requirements.require_text(self.layer, "audit layer")
        requirements.require_nonnegative_int(self.count, "audit layer count")


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceLayerCountInventory:
    """Own unique layer counts in canonical layer-name order."""

    _counts: tuple[ReferenceEvidenceLayerCount, ...] = field(repr=False)

    def __init__(self, *counts: ReferenceEvidenceLayerCount) -> None:
        values = tuple(counts)
        if len(values) > REFERENCE_EVIDENCE_LIMITS.maximum_layer_counts:
            raise ValueError("audit audited_layer_counts is too large")
        if any(
            not isinstance(item, ReferenceEvidenceLayerCount) for item in values
        ):
            raise TypeError("audit layer counts contain an unsupported value")
        layers = tuple(item.layer for item in values)
        if tuple(sorted(layers)) != layers or len(set(layers)) != len(layers):
            raise ValueError("audit layer counts must be unique and sorted")
        object.__setattr__(self, "_counts", values)

    def __iter__(self) -> Iterator[ReferenceEvidenceLayerCount]:
        return iter(self._counts)

    def __len__(self) -> int:
        return len(self._counts)

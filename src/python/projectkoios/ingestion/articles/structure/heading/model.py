"""Article-structure heading model."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.structure import (
    StructureKind,
)


@dataclass(frozen=True)
class _Heading:
    kind: StructureKind
    level: int
    label: str | None
    title: str
    evidence_type: str
    confidence: float

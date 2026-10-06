"""Article-structure proposal model."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.models import (
    Metadata,
    SourceSpan,
)
from projectkoios.ingestion.structure import (
    StructureEvidenceStatus,
    StructureKind,
)


@dataclass
class _Proposal:
    key: str
    kind: StructureKind
    source_spans: tuple[SourceSpan, ...]
    source_block_ids: tuple[str, ...]
    source_key: tuple[int, int, int]
    evidence_type: str
    confidence: float
    title: str | None = None
    label: str | None = None
    heading_level: int | None = None
    heading_confidence: float | None = None
    reading_order: int | None = None
    reading_order_confidence: float | None = None
    evidence_status: StructureEvidenceStatus = StructureEvidenceStatus.PROPOSED
    evidence: Metadata = ()
    parent_key: str | None = None
    warning_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _WarningProposal:
    key: str
    code: str
    message: str
    proposal_keys: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    object_ids: tuple[str, ...] = ()
    evidence: Metadata = ()

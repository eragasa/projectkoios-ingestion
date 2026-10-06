"""Article-structure proposal factory."""

from __future__ import annotations

from projectkoios.ingestion.articles.structure.evidence.span import (
    _ordered_unique_spans,
)
from projectkoios.ingestion.articles.structure.evidence.text import (
    _TextEvidence,
)
from projectkoios.ingestion.articles.structure.proposal.model import _Proposal
from projectkoios.ingestion.models import (
    Metadata,
)
from projectkoios.ingestion.structure import (
    StructureEvidenceStatus,
    StructureKind,
)


def _proposal_from_evidence(
    *,
    key: str,
    kind: StructureKind,
    items: tuple[_TextEvidence, ...],
    evidence_type: str,
    confidence: float,
    title: str | None = None,
    label: str | None = None,
    heading_level: int | None = None,
    heading_confidence: float | None = None,
    evidence_status: StructureEvidenceStatus = StructureEvidenceStatus.PROPOSED,
    evidence: Metadata = (),
) -> _Proposal:
    return _Proposal(
        key=key,
        kind=kind,
        source_spans=_ordered_unique_spans(
            span for item in items for span in item.block.source_spans
        ),
        source_block_ids=tuple(item.block.block_id for item in items),
        source_key=min(item.source_key for item in items),
        evidence_type=evidence_type,
        confidence=confidence,
        title=title,
        label=label,
        heading_level=heading_level,
        heading_confidence=heading_confidence,
        reading_order_confidence=min(item.reading_confidence for item in items),
        evidence_status=evidence_status,
        evidence=evidence,
    )

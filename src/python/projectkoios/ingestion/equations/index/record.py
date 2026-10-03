"""One deterministic equation index record."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.equations.index.identity import (
    EQUATION_INDEX_CONTRACT_VERSION,
)
from projectkoios.ingestion.equations.index.tier import EquationIndexTier
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import BoundingBox, SourceSpan


@dataclass(frozen=True)
class EquationIndexRecord:
    """Compact retrieval evidence without equation-image bytes."""

    record_id: str
    assembly_id: str
    candidate_ids: tuple[str, ...]
    tier: EquationIndexTier
    completeness: float
    reasons: tuple[str, ...]
    page_index: int
    printed_page_label: str | None
    source_block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    source_bounding_box: BoundingBox
    rendered_region_id: str
    rendered_region_sha256: str
    raw_fragments: tuple[str, ...]
    sanitized_native_text: str
    latex_proposal: str | None
    mathml_proposal: str | None
    preceding_context_text: str | None
    following_context_text: str | None
    retrieval_text: str
    contract_version: str = EQUATION_INDEX_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_INDEX_CONTRACT_VERSION:
            raise ValueError("unsupported equation index record version")
        if not 0.0 <= self.completeness <= 1.0:
            raise ValueError("equation completeness must be in [0, 1]")
        expected = stable_id(
            "equation-index-record",
            EQUATION_INDEX_CONTRACT_VERSION,
            self.assembly_id,
            self.tier,
            self.completeness,
            self.reasons,
            self.retrieval_text,
        )
        if self.record_id != expected:
            raise ValueError("equation index record ID is inconsistent")

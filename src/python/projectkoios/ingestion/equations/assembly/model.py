"""One deterministic equation assembly."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.equations.assembly.identity import (
    EQUATION_ASSEMBLY_CONTRACT_VERSION,
    equation_assembly_id,
)
from projectkoios.ingestion.equations.assembly.kind import EquationAssemblyKind
from projectkoios.ingestion.equations.detection import EquationEvidenceStatus
from projectkoios.ingestion.models import SourceSpan
from projectkoios.ingestion.pdf.models import RenderedRegion


@dataclass(frozen=True)
class EquationAssembly:
    """Exact grouped detector evidence and its rendered representation."""

    assembly_id: str
    detection_result_id: str
    candidate_ids: tuple[str, ...]
    detector_evidence_statuses: tuple[EquationEvidenceStatus, ...]
    kind: EquationAssemblyKind
    page_index: int
    printed_page_label: str | None
    source_spans: tuple[SourceSpan, ...]
    source_block_ids: tuple[str, ...]
    raw_fragments: tuple[str, ...]
    sanitized_native_text: str
    control_character_count: int
    source_labels: tuple[str, ...]
    preceding_context_text: str | None
    following_context_text: str | None
    rendered_region: RenderedRegion
    prefilter_reasons: tuple[str, ...]
    rejected: bool
    contract_version: str = EQUATION_ASSEMBLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_ASSEMBLY_CONTRACT_VERSION:
            raise ValueError("unsupported equation assembly version")
        if not self.candidate_ids or len(self.candidate_ids) != len(
            set(self.candidate_ids)
        ):
            raise ValueError(
                "assembly candidate IDs must be non-empty and unique"
            )
        if not self.raw_fragments:
            raise ValueError("assembly must retain raw fragments")
        if len(self.detector_evidence_statuses) != len(self.candidate_ids):
            raise ValueError("assembly detector statuses must match candidates")
        if self.page_index < 0:
            raise ValueError("assembly page index must be non-negative")
        if self.control_character_count < 0:
            raise ValueError("control-character count must be non-negative")
        expected = equation_assembly_id(
            self.detection_result_id,
            self.candidate_ids,
            self.detector_evidence_statuses,
            self.rendered_region.region_id,
            self.sanitized_native_text,
            self.prefilter_reasons,
            self.rejected,
        )
        if self.assembly_id != expected:
            raise ValueError("equation assembly ID is inconsistent")

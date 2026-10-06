from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.tables import TableCandidate
from projectkoios.ingestion.tables.structure.model import TableStructure
from projectkoios.ingestion.tables.structure.status.evidence import (
    TableStructureEvidenceStatus,
)
from projectkoios.ingestion.transcription.derivation.model import (
    TranscriptionDerivation,
)
from projectkoios.ingestion.transcription.kind.item import TranscriptionItemKind
from projectkoios.ingestion.transcription.kind.source.object import (
    TranscriptionSourceObjectKind,
)
from projectkoios.ingestion.transcription.status.evidence import (
    TranscriptionEvidenceStatus,
)


@dataclass(frozen=True)
class TableTranscriptionDerivation(TranscriptionDerivation):
    @classmethod
    def derive(
        cls,
        structure: TableStructure,
        candidate: TableCandidate,
        printed_page_label: str | None,
    ) -> TableTranscriptionDerivation:
        block_ids = cls.deduplicate_strings(
            tuple(
                block_id
                for region in candidate.regions
                for block_id in region.block_ids
            )
            + tuple(
                association.block_id for association in candidate.associations
            )
            + tuple(
                block_id
                for cell in structure.cells
                for block_id in cell.source_block_ids
            )
        )
        spans = cls.deduplicate_spans(
            candidate.source_spans
            + tuple(span for row in structure.rows for span in row.source_spans)
            + tuple(
                span for cell in structure.cells for span in cell.source_spans
            )
        )
        status = (
            TranscriptionEvidenceStatus.AMBIGUOUS
            if structure.evidence_status
            is TableStructureEvidenceStatus.AMBIGUOUS
            else TranscriptionEvidenceStatus.PROPOSED
        )
        return cls(
            item_kind=TranscriptionItemKind.TABLE,
            source_object_kind=TranscriptionSourceObjectKind.TABLE_STRUCTURE,
            source_object_id=structure.structure_id,
            page_index=min(region.page_index for region in candidate.regions),
            printed_page_label=printed_page_label,
            source_block_ids=block_ids,
            source_spans=spans,
            source_texts=(),
            evidence_status=status,
            confidence=structure.confidence,
            structure_reading_order=None,
            evidence=(("candidate_id", candidate.candidate_id),),
        )

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.figures import FigureCandidate, FigureEvidenceStatus
from projectkoios.ingestion.transcription.derivation.transcription import (
    TranscriptionDerivation,
)
from projectkoios.ingestion.transcription.evidence.status import (
    TranscriptionEvidenceStatus,
)
from projectkoios.ingestion.transcription.item.kind import TranscriptionItemKind
from projectkoios.ingestion.transcription.source.object_kind import (
    TranscriptionSourceObjectKind,
)


@dataclass(frozen=True)
class FigureTranscriptionDerivation(TranscriptionDerivation):
    @classmethod
    def derive(
        cls, candidate: FigureCandidate, printed_page_label: str | None
    ) -> FigureTranscriptionDerivation:
        block_ids = cls.deduplicate_strings(
            tuple(
                block_id
                for component in candidate.components
                for block_id in component.source_block_ids
            )
            + tuple(
                association.block_id for association in candidate.associations
            )
        )
        status = (
            TranscriptionEvidenceStatus.AMBIGUOUS
            if candidate.evidence_status is FigureEvidenceStatus.AMBIGUOUS
            else TranscriptionEvidenceStatus.PROPOSED
        )
        return cls(
            item_kind=TranscriptionItemKind.FIGURE,
            source_object_kind=TranscriptionSourceObjectKind.FIGURE_CANDIDATE,
            source_object_id=candidate.candidate_id,
            page_index=candidate.page_index,
            printed_page_label=printed_page_label,
            source_block_ids=block_ids,
            source_spans=candidate.source_spans,
            source_texts=(),
            evidence_status=status,
            confidence=candidate.confidence,
            structure_reading_order=None,
            evidence=(("component_count", str(len(candidate.components))),),
        )

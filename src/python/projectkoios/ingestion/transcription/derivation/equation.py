from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.equations.detection import (
    EquationCandidate,
    EquationEvidenceStatus,
)
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
class EquationTranscriptionDerivation(TranscriptionDerivation):
    @classmethod
    def derive(
        cls, candidate: EquationCandidate, printed_page_label: str | None
    ) -> EquationTranscriptionDerivation:
        page_index = candidate.source_spans[0].page_index
        status = (
            TranscriptionEvidenceStatus.AMBIGUOUS
            if candidate.evidence_status is EquationEvidenceStatus.AMBIGUOUS
            else TranscriptionEvidenceStatus.PROPOSED
        )
        return cls(
            item_kind=TranscriptionItemKind.EQUATION,
            source_object_kind=TranscriptionSourceObjectKind.EQUATION_CANDIDATE,
            source_object_id=candidate.candidate_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            source_block_ids=(candidate.source_block_id,),
            source_spans=candidate.source_spans,
            source_texts=(candidate.raw_text,),
            evidence_status=status,
            confidence=candidate.confidence,
            structure_reading_order=None,
            evidence=(("candidate_kind", candidate.kind.value),),
        )

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.models import ExtractedBlock
from projectkoios.ingestion.transcription.derivation.transcription import (
    TranscriptionDerivation,
)
from projectkoios.ingestion.transcription.evidence_status import (
    TranscriptionEvidenceStatus,
)
from projectkoios.ingestion.transcription.item_kind import TranscriptionItemKind
from projectkoios.ingestion.transcription.source_object_kind import (
    TranscriptionSourceObjectKind,
)


@dataclass(frozen=True)
class RawBlockTranscriptionDerivation(TranscriptionDerivation):
    @classmethod
    def derive(
        cls,
        page_index: int,
        printed_page_label: str | None,
        block: ExtractedBlock,
    ) -> RawBlockTranscriptionDerivation:
        if block.text is None:
            raise ValueError("raw-block derivation requires text")
        return cls(
            item_kind=TranscriptionItemKind.PROSE,
            source_object_kind=TranscriptionSourceObjectKind.RAW_BLOCK,
            source_object_id=block.block_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            source_block_ids=(block.block_id,),
            source_spans=block.source_spans,
            source_texts=(block.text,),
            evidence_status=TranscriptionEvidenceStatus.OBSERVED_SOURCE_TRANSFORM,
            confidence=block.confidence,
            structure_reading_order=None,
            evidence=(("fallback", "raw_block"),),
            warning_codes=("transcription.raw_block_fallback",),
        )

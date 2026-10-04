from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.models import ExtractedBlock
from projectkoios.ingestion.structure import StructureNode
from projectkoios.ingestion.transcription.derivation.structure_disposition import (  # noqa: E501
    TranscriptionStructureDisposition,
)
from projectkoios.ingestion.transcription.derivation.transcription import (
    TranscriptionDerivation,
)
from projectkoios.ingestion.transcription.source.object_kind import (
    TranscriptionSourceObjectKind,
)


@dataclass(frozen=True)
class StructureTranscriptionDerivation(TranscriptionDerivation):
    @classmethod
    def derive(
        cls,
        node: StructureNode,
        blocks: tuple[ExtractedBlock, ...],
        page_label_by_index: dict[int, str | None],
    ) -> StructureTranscriptionDerivation:
        disposition = TranscriptionStructureDisposition.derive(node)
        if disposition.item_kind is None:
            raise ValueError(
                "structure node does not produce a transcription item"
            )
        spans = cls.deduplicate_spans(
            tuple(span for block in blocks for span in block.source_spans)
        )
        page_index = min(span.page_index for span in spans)
        return cls(
            item_kind=disposition.item_kind,
            source_object_kind=TranscriptionSourceObjectKind.STRUCTURE_NODE,
            source_object_id=node.node_id,
            page_index=page_index,
            printed_page_label=page_label_by_index[page_index],
            source_block_ids=tuple(block.block_id for block in blocks),
            source_spans=spans,
            source_texts=tuple(
                block.text for block in blocks if block.text is not None
            ),
            evidence_status=disposition.evidence_status,
            confidence=node.confidence,
            structure_reading_order=node.reading_order,
            evidence=(("structure_kind", node.kind.value),),
        )

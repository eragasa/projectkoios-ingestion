from __future__ import annotations

import math
from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractDerivation
from projectkoios.ingestion.equations.detection import (
    EquationCandidate,
    EquationEvidenceStatus,
)
from projectkoios.ingestion.figures import (
    FigureCandidate,
    FigureEvidenceStatus,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    IngestionWarning,
    Metadata,
    SourceSpan,
    WarningSeverity,
)
from projectkoios.ingestion.structure import (
    StructureEvidenceStatus,
    StructureKind,
    StructureNode,
)
from projectkoios.ingestion.tables import TableCandidate
from projectkoios.ingestion.tables.structure.evidence_status import (
    TableStructureEvidenceStatus,
)
from projectkoios.ingestion.tables.structure.structure import TableStructure
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.evidence.status import (
    TranscriptionEvidenceStatus,
)
from projectkoios.ingestion.transcription.item.item import TranscriptionItem
from projectkoios.ingestion.transcription.item_kind import (
    TranscriptionItemKind,
)
from projectkoios.ingestion.transcription.order.status import (
    TranscriptionOrderStatus,
)
from projectkoios.ingestion.transcription.source.object_kind import (
    TranscriptionSourceObjectKind,
)


@dataclass(frozen=True)
class TranscriptionDerivation(
    AbstractDerivation, AbstractTranscriptionDataObject
):
    item_kind: TranscriptionItemKind
    source_object_kind: TranscriptionSourceObjectKind
    source_object_id: str
    page_index: int
    printed_page_label: str | None
    source_block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    source_texts: tuple[str, ...]
    evidence_status: TranscriptionEvidenceStatus
    confidence: float | None
    structure_reading_order: int | None
    evidence: Metadata
    warning_codes: tuple[str, ...] = ()

    @property
    def item_id(self) -> str:
        normalized = (
            AbstractTranscriptionDataObject._normalize_text(self.source_texts)
            if self.source_texts
            else None
        )
        method = (
            AbstractTranscriptionDataObject.NORMALIZATION_METHOD
            if self.source_texts
            else None
        )
        return TranscriptionItem._item_id(
            self.item_kind,
            self.source_object_kind,
            self.source_object_id,
            self.page_index,
            self.source_block_ids,
            self.source_spans,
            normalized,
            self.source_texts,
            method,
            self.evidence_status,
            self.confidence,
            self.evidence,
        )

    @staticmethod
    def _page_anchor_draft(
        document: ExtractedDocument, page: ExtractedPage
    ) -> TranscriptionDerivation:
        object_id = stable_id(
            "transcription-page-anchor",
            document.source.source_id,
            document.source.blob_id,
            page.page_index,
        )
        return TranscriptionDerivation(
            item_kind=TranscriptionItemKind.PAGE_ANCHOR,
            source_object_kind=TranscriptionSourceObjectKind.PAGE,
            source_object_id=object_id,
            page_index=page.page_index,
            printed_page_label=page.printed_page_label,
            source_block_ids=(),
            source_spans=(),
            source_texts=(),
            evidence_status=TranscriptionEvidenceStatus.OBSERVED_SOURCE_TRANSFORM,
            confidence=None,
            structure_reading_order=None,
            evidence=(("page_index", str(page.page_index)),),
        )

    @staticmethod
    def _structure_draft(
        node: StructureNode,
        blocks: tuple[ExtractedBlock, ...],
        item_kind: TranscriptionItemKind,
        page_label_by_index: dict[int, str | None],
    ) -> TranscriptionDerivation:
        spans = AbstractTranscriptionDataObject._deduplicate_spans(
            tuple(span for block in blocks for span in block.source_spans)
        )
        page_index = min(span.page_index for span in spans)
        label = page_label_by_index[page_index]
        return TranscriptionDerivation(
            item_kind=item_kind,
            source_object_kind=TranscriptionSourceObjectKind.STRUCTURE_NODE,
            source_object_id=node.node_id,
            page_index=page_index,
            printed_page_label=label,
            source_block_ids=tuple(block.block_id for block in blocks),
            source_spans=spans,
            source_texts=tuple(
                block.text for block in blocks if block.text is not None
            ),
            evidence_status=TranscriptionDerivation._structure_status(node),
            confidence=node.confidence,
            structure_reading_order=node.reading_order,
            evidence=(("structure_kind", node.kind.value),),
        )

    @staticmethod
    def _raw_block_draft(
        page_index: int,
        printed_page_label: str | None,
        block: ExtractedBlock,
    ) -> TranscriptionDerivation:
        assert block.text is not None
        return TranscriptionDerivation(
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

    @staticmethod
    def _item_kind_for_node(
        node: StructureNode,
    ) -> TranscriptionItemKind | None:
        if node.kind in (
            StructureKind.TITLE,
            StructureKind.PART,
            StructureKind.CHAPTER,
            StructureKind.SECTION,
            StructureKind.SUBSECTION,
            StructureKind.APPENDIX,
        ):
            return TranscriptionItemKind.HEADING
        if node.kind is StructureKind.EQUATION:
            return TranscriptionItemKind.EQUATION
        if node.kind is StructureKind.TABLE:
            return TranscriptionItemKind.TABLE
        if node.kind is StructureKind.FIGURE:
            return TranscriptionItemKind.FIGURE
        if node.kind in (
            StructureKind.DOCUMENT,
            StructureKind.FRONT_MATTER,
            StructureKind.PROBLEM_SET,
            StructureKind.BIBLIOGRAPHY,
            StructureKind.INDEX,
        ):
            return None
        return TranscriptionItemKind.PROSE

    @staticmethod
    def _draft_order_key(
        draft: TranscriptionDerivation,
        block_position: dict[str, tuple[int, int]],
    ) -> tuple[object, ...]:
        if draft.item_kind is TranscriptionItemKind.PAGE_ANCHOR:
            return (draft.page_index, 0, 0.0, 0.0, 0, draft.source_object_id)
        boxes = tuple(
            span.bounding_box
            for span in draft.source_spans
            if span.page_index == draft.page_index
            and span.bounding_box is not None
        )
        if boxes:
            y = min(box[1] for box in boxes)
            x = min(box[0] for box in boxes)
            fallback = 0
        elif draft.structure_reading_order is not None:
            y = float(draft.structure_reading_order)
            x = 0.0
            fallback = 1
        else:
            positions = tuple(
                block_position[block_id][1]
                for block_id in draft.source_block_ids
                if block_id in block_position
            )
            y = float(min(positions)) if positions else math.inf
            x = 0.0
            fallback = 2
        priority = {
            TranscriptionItemKind.HEADING: 0,
            TranscriptionItemKind.PROSE: 1,
            TranscriptionItemKind.EQUATION: 2,
            TranscriptionItemKind.TABLE: 3,
            TranscriptionItemKind.FIGURE: 4,
            TranscriptionItemKind.PAGE_ANCHOR: 0,
        }[draft.item_kind]
        return (
            draft.page_index,
            1,
            fallback,
            y,
            x,
            priority,
            draft.source_object_id,
        )

    @staticmethod
    def _draft_order_status(
        draft: TranscriptionDerivation,
    ) -> TranscriptionOrderStatus:
        if draft.item_kind is TranscriptionItemKind.PAGE_ANCHOR:
            return TranscriptionOrderStatus.PAGE_ANCHOR
        if any(
            span.page_index == draft.page_index
            and span.bounding_box is not None
            for span in draft.source_spans
        ):
            return TranscriptionOrderStatus.PROPOSED_GEOMETRIC
        if draft.structure_reading_order is not None:
            return TranscriptionOrderStatus.PROPOSED_STRUCTURE
        return TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER

    @staticmethod
    def _draft_warning(
        draft: TranscriptionDerivation, code: str
    ) -> IngestionWarning:
        if code == "transcription.order_uncertain":
            message = (
                "Item ordering uses uncertain extractor source order because "
                "geometry and structure order are unavailable."
            )
        else:
            message = (
                "Raw text is included as an explicit fallback because no "
                "selected structure item represents the block."
            )
        return IngestionWarning.create(
            code=code,
            severity=WarningSeverity.WARNING,
            message=message,
            object_ids=(draft.source_object_id,),
            source_spans=draft.source_spans,
            evidence=(("item_kind", draft.item_kind.value),),
        )

    @staticmethod
    def _table_projection(
        structure: TableStructure,
        candidate: TableCandidate,
    ) -> tuple[tuple[str, ...], tuple[SourceSpan, ...]]:
        block_ids = AbstractTranscriptionDataObject._deduplicate_strings(
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
        spans = AbstractTranscriptionDataObject._deduplicate_spans(
            candidate.source_spans
            + tuple(span for row in structure.rows for span in row.source_spans)
            + tuple(
                span for cell in structure.cells for span in cell.source_spans
            )
        )
        return block_ids, spans

    @staticmethod
    def _figure_projection(
        candidate: FigureCandidate,
    ) -> tuple[tuple[str, ...], tuple[SourceSpan, ...]]:
        block_ids = AbstractTranscriptionDataObject._deduplicate_strings(
            tuple(
                block_id
                for component in candidate.components
                for block_id in component.source_block_ids
            )
            + tuple(
                association.block_id for association in candidate.associations
            )
        )
        return block_ids, candidate.source_spans

    @staticmethod
    def _equation_status(
        candidate: EquationCandidate,
    ) -> TranscriptionEvidenceStatus:
        if candidate.evidence_status is EquationEvidenceStatus.AMBIGUOUS:
            return TranscriptionEvidenceStatus.AMBIGUOUS
        return TranscriptionEvidenceStatus.PROPOSED

    @staticmethod
    def _table_status(structure: TableStructure) -> TranscriptionEvidenceStatus:
        if structure.evidence_status is TableStructureEvidenceStatus.AMBIGUOUS:
            return TranscriptionEvidenceStatus.AMBIGUOUS
        return TranscriptionEvidenceStatus.PROPOSED

    @staticmethod
    def _figure_status(
        candidate: FigureCandidate,
    ) -> TranscriptionEvidenceStatus:
        if candidate.evidence_status is FigureEvidenceStatus.AMBIGUOUS:
            return TranscriptionEvidenceStatus.AMBIGUOUS
        return TranscriptionEvidenceStatus.PROPOSED

    @staticmethod
    def _structure_status(node: StructureNode) -> TranscriptionEvidenceStatus:
        if node.evidence_status is StructureEvidenceStatus.UNCERTAIN:
            return TranscriptionEvidenceStatus.AMBIGUOUS
        return TranscriptionEvidenceStatus.PROPOSED

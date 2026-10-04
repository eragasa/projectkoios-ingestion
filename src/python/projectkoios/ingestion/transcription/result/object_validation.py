from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    IngestionWarning,
    SourceSpan,
)
from projectkoios.ingestion.structure import (
    StructureNode,
)
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.derivation.transcription import (
    TranscriptionDerivation,
)
from projectkoios.ingestion.transcription.evidence.status import (
    TranscriptionEvidenceStatus,
)
from projectkoios.ingestion.transcription.item.item import TranscriptionItem
from projectkoios.ingestion.transcription.item_kind import (
    TranscriptionItemKind,
)
from projectkoios.ingestion.transcription.omission_reason import (
    TranscriptionOmissionReason,
)
from projectkoios.ingestion.transcription.order.status import (
    TranscriptionOrderStatus,
)
from projectkoios.ingestion.transcription.result.result import (
    StructuredTranscriptionResult,
)
from projectkoios.ingestion.transcription.source.object_kind import (
    TranscriptionSourceObjectKind,
)


@dataclass(frozen=True)
class TranscriptionResultObjectValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    result_id: str
    validated_item_count: int
    validated_omission_count: int
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def create(
        cls, result: StructuredTranscriptionResult
    ) -> TranscriptionResultObjectValidation:
        cls._validate_result_objects(result)
        return cls(result.result_id, len(result.items), len(result.omissions))

    @staticmethod
    def _validate_result_objects(result: StructuredTranscriptionResult) -> None:
        transcription_input = result.transcription_input
        document = transcription_input.document
        page_by_index = {page.page_index: page for page in document.pages}
        block_by_id = {
            block.block_id: block
            for page in document.pages
            for block in page.blocks
        }
        node_by_id = {
            node.node_id: node
            for node in transcription_input.structure_analysis.nodes
        }
        equation_candidates = (
            transcription_input.equation_detection_result.candidates
        )
        equation_by_id = {
            candidate.candidate_id: candidate
            for candidate in equation_candidates
        }
        table_result = transcription_input.table_structure_result
        table_by_id = {
            structure.structure_id: structure
            for structure in table_result.structures
        }
        table_candidates = (
            table_result.structure_input.detection_result.candidates
        )
        table_candidate_by_id = {
            candidate.candidate_id: candidate for candidate in table_candidates
        }
        figure_by_id = {
            candidate.candidate_id: candidate
            for candidate in (
                transcription_input.figure_detection_result.candidates
            )
        }
        warning_by_id = {
            warning.warning_id: warning for warning in result.warnings
        }
        page_by_anchor_id = {
            stable_id(
                "transcription-page-anchor",
                document.source.source_id,
                document.source.blob_id,
                page.page_index,
            ): page
            for page in document.pages
        }
        for item in result.items:
            page = page_by_index.get(item.page_index)
            if page is None:
                raise ValueError("transcription item page is unresolved")
            if item.printed_page_label != page.printed_page_label:
                raise ValueError(
                    "transcription item printed page label is stale"
                )
            if not set(item.source_block_ids).issubset(block_by_id):
                raise ValueError(
                    "transcription item source block is unresolved"
                )
            AbstractTranscriptionDataObject._validate_exact_source_spans(
                item.source_spans, document
            )
            if item.source_object_kind is TranscriptionSourceObjectKind.PAGE:
                source_page = page_by_anchor_id.get(item.source_object_id)
                if (
                    source_page is None
                    or source_page.page_index != item.page_index
                ):
                    raise ValueError("transcription page anchor is unresolved")
                if (
                    item.item_kind is not TranscriptionItemKind.PAGE_ANCHOR
                    or item.source_block_ids
                    or item.source_spans
                    or item.source_texts
                    or item.confidence is not None
                    or item.order_status
                    is not TranscriptionOrderStatus.PAGE_ANCHOR
                    or item.evidence_status
                    is not TranscriptionEvidenceStatus.OBSERVED_SOURCE_TRANSFORM
                ):
                    raise ValueError(
                        "transcription page anchor is inconsistent"
                    )
            elif (
                item.source_object_kind
                is TranscriptionSourceObjectKind.RAW_BLOCK
            ):
                block = block_by_id.get(item.source_object_id)
                if block is None or block.text is None:
                    raise ValueError("transcription raw block is unresolved")
                TranscriptionResultObjectValidation._validate_item_projection(
                    item,
                    expected_kind=TranscriptionItemKind.PROSE,
                    expected_block_ids=(block.block_id,),
                    expected_spans=block.source_spans,
                    expected_texts=(block.text,),
                    expected_confidence=block.confidence,
                    expected_status=(
                        TranscriptionEvidenceStatus.OBSERVED_SOURCE_TRANSFORM
                    ),
                )
                if "transcription.raw_block_fallback" not in {
                    warning_by_id[warning_id].code
                    for warning_id in item.warning_ids
                }:
                    raise ValueError("raw-block fallback lacks a warning")
            elif (
                item.source_object_kind
                is TranscriptionSourceObjectKind.STRUCTURE_NODE
            ):
                node = node_by_id.get(item.source_object_id)
                expected_kind = (
                    TranscriptionDerivation._item_kind_for_node(node)
                    if node is not None
                    else None
                )
                if (
                    node is None
                    or expected_kind is None
                    or not set(item.source_block_ids).issubset(
                        node.source_block_ids
                    )
                ):
                    raise ValueError(
                        "transcription structure node is unresolved"
                    )
                blocks = tuple(
                    block_by_id[value] for value in item.source_block_ids
                )
                TranscriptionResultObjectValidation._validate_item_projection(
                    item,
                    expected_kind=expected_kind,
                    expected_block_ids=item.source_block_ids,
                    expected_spans=AbstractTranscriptionDataObject._deduplicate_spans(
                        tuple(
                            span
                            for block in blocks
                            for span in block.source_spans
                        )
                    ),
                    expected_texts=tuple(
                        block.text for block in blocks if block.text is not None
                    ),
                    expected_confidence=node.confidence,
                    expected_status=TranscriptionDerivation._structure_status(
                        node
                    ),
                )
            elif (
                item.source_object_kind
                is TranscriptionSourceObjectKind.EQUATION_CANDIDATE
            ):
                equation_candidate = equation_by_id.get(item.source_object_id)
                if equation_candidate is None:
                    raise ValueError(
                        "transcription equation candidate is unresolved"
                    )
                TranscriptionResultObjectValidation._validate_item_projection(
                    item,
                    expected_kind=TranscriptionItemKind.EQUATION,
                    expected_block_ids=(equation_candidate.source_block_id,),
                    expected_spans=equation_candidate.source_spans,
                    expected_texts=(equation_candidate.raw_text,),
                    expected_confidence=equation_candidate.confidence,
                    expected_status=TranscriptionDerivation._equation_status(
                        equation_candidate
                    ),
                )
            elif (
                item.source_object_kind
                is TranscriptionSourceObjectKind.TABLE_STRUCTURE
            ):
                structure = table_by_id.get(item.source_object_id)
                if structure is None:
                    raise ValueError(
                        "transcription table structure is unresolved"
                    )
                table_candidate = table_candidate_by_id[structure.candidate_id]
                block_ids, spans = TranscriptionDerivation._table_projection(
                    structure, table_candidate
                )
                TranscriptionResultObjectValidation._validate_item_projection(
                    item,
                    expected_kind=TranscriptionItemKind.TABLE,
                    expected_block_ids=block_ids,
                    expected_spans=spans,
                    expected_texts=(),
                    expected_confidence=structure.confidence,
                    expected_status=TranscriptionDerivation._table_status(
                        structure
                    ),
                )
            else:
                figure_candidate = figure_by_id.get(item.source_object_id)
                if figure_candidate is None:
                    raise ValueError(
                        "transcription figure candidate is unresolved"
                    )
                block_ids, spans = TranscriptionDerivation._figure_projection(
                    figure_candidate
                )
                TranscriptionResultObjectValidation._validate_item_projection(
                    item,
                    expected_kind=TranscriptionItemKind.FIGURE,
                    expected_block_ids=block_ids,
                    expected_spans=spans,
                    expected_texts=(),
                    expected_confidence=figure_candidate.confidence,
                    expected_status=TranscriptionDerivation._figure_status(
                        figure_candidate
                    ),
                )
            structure_node = (
                node_by_id.get(item.source_object_id)
                if item.source_object_kind
                is TranscriptionSourceObjectKind.STRUCTURE_NODE
                else None
            )
            TranscriptionResultObjectValidation._validate_item_order_evidence(
                item, structure_node, warning_by_id
            )
        page_anchor_indices = tuple(
            item.page_index
            for item in result.items
            if item.item_kind is TranscriptionItemKind.PAGE_ANCHOR
        )
        if page_anchor_indices != tuple(page_by_index):
            raise ValueError("transcription page anchors are incomplete")
        for source_kind, expected_ids in (
            (
                TranscriptionSourceObjectKind.EQUATION_CANDIDATE,
                set(equation_by_id),
            ),
            (TranscriptionSourceObjectKind.TABLE_STRUCTURE, set(table_by_id)),
            (TranscriptionSourceObjectKind.FIGURE_CANDIDATE, set(figure_by_id)),
        ):
            actual_ids = {
                item.source_object_id
                for item in result.items
                if item.source_object_kind is source_kind
            }
            if actual_ids != expected_ids:
                raise ValueError(
                    "transcription typed-object coverage is incomplete"
                )
        item_by_id = {item.item_id: item for item in result.items}
        typed_source_kinds = {
            TranscriptionSourceObjectKind.EQUATION_CANDIDATE,
            TranscriptionSourceObjectKind.TABLE_STRUCTURE,
            TranscriptionSourceObjectKind.FIGURE_CANDIDATE,
        }
        for omission in result.omissions:
            block = block_by_id.get(omission.source_block_id)
            if block is None or omission.source_spans != block.source_spans:
                raise ValueError(
                    "transcription omission source block is unresolved"
                )
            if omission.omitted_object_id != block.block_id:
                node = node_by_id.get(omission.omitted_object_id)
                if node is None or block.block_id not in node.source_block_ids:
                    raise ValueError(
                        "transcription omitted object is unresolved"
                    )
            linked_items = tuple(
                item_by_id[item_id]
                for item_id in omission.represented_by_item_ids
            )
            if any(
                block.block_id not in item.source_block_ids
                for item in linked_items
            ):
                raise ValueError(
                    "transcription omission replacement does not cover "
                    "its block"
                )
            if omission.reason is (
                TranscriptionOmissionReason.REPRESENTED_BY_TYPED_OBJECT
            ) and not any(
                item.source_object_kind in typed_source_kinds
                for item in linked_items
            ):
                raise ValueError(
                    "typed-object omission lacks a typed replacement"
                )
            if omission.reason is (
                TranscriptionOmissionReason.REPRESENTED_BY_EARLIER_ITEM
            ) and any(
                item.source_object_kind in typed_source_kinds
                for item in linked_items
            ):
                raise ValueError(
                    "earlier-item omission has a typed replacement"
                )
            if (
                omission.reason
                in (
                    TranscriptionOmissionReason.NO_TEXT_PAYLOAD,
                    TranscriptionOmissionReason.UNREPRESENTED_NON_TEXT_BLOCK,
                )
                and block.text is not None
            ):
                raise ValueError("non-text omission refers to a text block")
            if (
                omission.reason
                is (TranscriptionOmissionReason.UNREPRESENTED_NON_TEXT_BLOCK)
                and omission.omitted_object_id != block.block_id
            ):
                raise ValueError(
                    "unrepresented omission must identify its block"
                )
        represented_node_ids = {
            item.source_object_id
            for item in result.items
            if item.source_object_kind
            is TranscriptionSourceObjectKind.STRUCTURE_NODE
        } | {item.omitted_object_id for item in result.omissions}
        expected_node_ids = {
            node.node_id
            for node in transcription_input.structure_analysis.nodes
            if TranscriptionDerivation._item_kind_for_node(node) is not None
            and node.source_block_ids
        }
        if not expected_node_ids.issubset(represented_node_ids):
            raise ValueError(
                "transcription structure-node coverage is incomplete"
            )
        represented_blocks = {
            block_id
            for item in result.items
            for block_id in item.source_block_ids
        } | {item.source_block_id for item in result.omissions}
        if represented_blocks != set(block_by_id):
            raise ValueError("transcription raw block coverage is incomplete")

    @staticmethod
    def _validate_item_order_evidence(
        item: TranscriptionItem,
        structure_node: StructureNode | None,
        warning_by_id: dict[str, IngestionWarning],
    ) -> None:
        if item.item_kind is TranscriptionItemKind.PAGE_ANCHOR:
            expected = TranscriptionOrderStatus.PAGE_ANCHOR
        elif any(
            span.page_index == item.page_index and span.bounding_box is not None
            for span in item.source_spans
        ):
            expected = TranscriptionOrderStatus.PROPOSED_GEOMETRIC
        elif (
            structure_node is not None
            and structure_node.reading_order is not None
        ):
            expected = TranscriptionOrderStatus.PROPOSED_STRUCTURE
        else:
            expected = TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER
        if item.order_status is not expected:
            raise ValueError(
                "transcription item order evidence is inconsistent"
            )
        warning_codes = {
            warning_by_id[warning_id].code for warning_id in item.warning_ids
        }
        if expected is TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER and (
            "transcription.order_uncertain" not in warning_codes
        ):
            raise ValueError("uncertain transcription order lacks a warning")

    @staticmethod
    def _validate_item_projection(
        item: TranscriptionItem,
        *,
        expected_kind: TranscriptionItemKind,
        expected_block_ids: tuple[str, ...],
        expected_spans: tuple[SourceSpan, ...],
        expected_texts: tuple[str, ...],
        expected_confidence: float,
        expected_status: TranscriptionEvidenceStatus,
    ) -> None:
        if (
            item.item_kind is not expected_kind
            or item.source_block_ids != expected_block_ids
            or item.source_spans != expected_spans
            or item.source_texts != expected_texts
            or item.confidence != expected_confidence
            or item.evidence_status is not expected_status
        ):
            raise ValueError("transcription item projection is inconsistent")

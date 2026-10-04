from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.derivation.structure_disposition import (  # noqa: E501
    TranscriptionStructureDisposition,
)
from projectkoios.ingestion.transcription.item.item import TranscriptionItem
from projectkoios.ingestion.transcription.omission.omission import (
    TranscriptionOmission,
)
from projectkoios.ingestion.transcription.omission.reason import (
    TranscriptionOmissionReason,
)
from projectkoios.ingestion.transcription.request.request import (
    StructuredTranscriptionRequest,
)
from projectkoios.ingestion.transcription.source.object_kind import (
    TranscriptionSourceObjectKind,
)


@dataclass(frozen=True)
class TranscriptionOmissionCoverageValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    transcription_input: StructuredTranscriptionRequest
    items: tuple[TranscriptionItem, ...]
    omissions: tuple[TranscriptionOmission, ...]
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported omission coverage validation version")
        document = self.transcription_input.document
        block_by_id = {
            block.block_id: block
            for page in document.pages
            for block in page.blocks
        }
        node_by_id = {
            node.node_id: node
            for node in self.transcription_input.structure_analysis.nodes
        }
        item_by_id = {item.item_id: item for item in self.items}
        typed_source_kinds = {
            TranscriptionSourceObjectKind.EQUATION_CANDIDATE,
            TranscriptionSourceObjectKind.TABLE_STRUCTURE,
            TranscriptionSourceObjectKind.FIGURE_CANDIDATE,
        }
        for omission in self.omissions:
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
                is TranscriptionOmissionReason.UNREPRESENTED_NON_TEXT_BLOCK
                and omission.omitted_object_id != block.block_id
            ):
                raise ValueError(
                    "unrepresented omission must identify its block"
                )
        represented_node_ids = {
            item.source_object_id
            for item in self.items
            if item.source_object_kind
            is TranscriptionSourceObjectKind.STRUCTURE_NODE
        } | {omission.omitted_object_id for omission in self.omissions}
        expected_node_ids = {
            node.node_id
            for node in self.transcription_input.structure_analysis.nodes
            if TranscriptionStructureDisposition.derive(node).item_kind
            is not None
            and node.source_block_ids
        }
        if not expected_node_ids.issubset(represented_node_ids):
            raise ValueError(
                "transcription structure-node coverage is incomplete"
            )
        represented_blocks = {
            block_id
            for item in self.items
            for block_id in item.source_block_ids
        } | {omission.source_block_id for omission in self.omissions}
        if represented_blocks != set(block_by_id):
            raise ValueError("transcription raw block coverage is incomplete")

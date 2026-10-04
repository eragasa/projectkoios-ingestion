from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractDerivation
from projectkoios.ingestion.models import SourceSpan
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.derivation.transcription import (
    TranscriptionDerivation,
)
from projectkoios.ingestion.transcription.item_kind import TranscriptionItemKind
from projectkoios.ingestion.transcription.order_status import (
    TranscriptionOrderStatus,
)


@dataclass(frozen=True)
class TranscriptionOrderDerivation(
    AbstractDerivation, AbstractTranscriptionDataObject
):
    item_id: str
    order_key: tuple[object, ...]
    order_status: TranscriptionOrderStatus
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def derive(
        cls,
        draft: TranscriptionDerivation,
        block_position: dict[str, tuple[int, int]],
    ) -> TranscriptionOrderDerivation:
        status = cls.status_for(
            draft.item_kind,
            draft.page_index,
            draft.source_spans,
            draft.structure_reading_order,
        )
        if status is TranscriptionOrderStatus.PAGE_ANCHOR:
            key: tuple[object, ...] = (
                draft.page_index,
                0,
                0.0,
                0.0,
                0,
                draft.source_object_id,
            )
        else:
            boxes = tuple(
                span.bounding_box
                for span in draft.source_spans
                if span.page_index == draft.page_index
                and span.bounding_box is not None
            )
            if status is TranscriptionOrderStatus.PROPOSED_GEOMETRIC:
                y = min(box[1] for box in boxes)
                x = min(box[0] for box in boxes)
                fallback = 0
            elif status is TranscriptionOrderStatus.PROPOSED_STRUCTURE:
                assert draft.structure_reading_order is not None
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
            key = (
                draft.page_index,
                1,
                fallback,
                y,
                x,
                priority,
                draft.source_object_id,
            )
        return cls(item_id=draft.item_id, order_key=key, order_status=status)

    @classmethod
    def status_for(
        cls,
        item_kind: TranscriptionItemKind,
        page_index: int,
        source_spans: Iterable[SourceSpan],
        structure_reading_order: int | None,
    ) -> TranscriptionOrderStatus:
        if item_kind is TranscriptionItemKind.PAGE_ANCHOR:
            return TranscriptionOrderStatus.PAGE_ANCHOR
        if any(
            span.page_index == page_index and span.bounding_box is not None
            for span in source_spans
        ):
            return TranscriptionOrderStatus.PROPOSED_GEOMETRIC
        if structure_reading_order is not None:
            return TranscriptionOrderStatus.PROPOSED_STRUCTURE
        return TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported transcription order derivation version"
            )
        self.validate_identity_fields(self.item_id)
        self.validate_tuple("transcription order key", self.order_key)
        if not isinstance(self.order_status, TranscriptionOrderStatus):
            raise TypeError("transcription order status is unsupported")

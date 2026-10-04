from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.models import IngestionWarning
from projectkoios.ingestion.structure import StructureNode
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.item.item import TranscriptionItem
from projectkoios.ingestion.transcription.item.kind import TranscriptionItemKind
from projectkoios.ingestion.transcription.order.status import (
    TranscriptionOrderStatus,
)


@dataclass(frozen=True)
class TranscriptionOrderValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    item: TranscriptionItem
    structure_node: StructureNode | None
    warnings: tuple[IngestionWarning, ...]
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported transcription order validation version"
            )
        if self.item.item_kind is TranscriptionItemKind.PAGE_ANCHOR:
            expected = TranscriptionOrderStatus.PAGE_ANCHOR
        elif any(
            span.page_index == self.item.page_index
            and span.bounding_box is not None
            for span in self.item.source_spans
        ):
            expected = TranscriptionOrderStatus.PROPOSED_GEOMETRIC
        elif (
            self.structure_node is not None
            and self.structure_node.reading_order is not None
        ):
            expected = TranscriptionOrderStatus.PROPOSED_STRUCTURE
        else:
            expected = TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER
        if self.item.order_status is not expected:
            raise ValueError(
                "transcription item order evidence is inconsistent"
            )
        warning_codes = {warning.code for warning in self.warnings}
        if expected is TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER and (
            "transcription.order_uncertain" not in warning_codes
        ):
            raise ValueError("uncertain transcription order lacks a warning")

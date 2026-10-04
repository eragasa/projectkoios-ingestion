from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.derivation.transcription import (
    TranscriptionDerivation,
)
from projectkoios.ingestion.transcription.item.item import TranscriptionItem


@dataclass(frozen=True)
class TranscriptionItemProjectionValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    item: TranscriptionItem
    derivation: TranscriptionDerivation
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported item projection validation version")
        if not isinstance(self.item, TranscriptionItem):
            raise TypeError("item projection validation requires an item")
        if not isinstance(self.derivation, TranscriptionDerivation):
            raise TypeError("item projection validation requires a derivation")
        if (
            self.item.item_kind is not self.derivation.item_kind
            or self.item.source_object_kind
            is not self.derivation.source_object_kind
            or self.item.source_object_id != self.derivation.source_object_id
            or self.item.page_index != self.derivation.page_index
            or self.item.source_block_ids != self.derivation.source_block_ids
            or self.item.source_spans != self.derivation.source_spans
            or self.item.source_texts != self.derivation.source_texts
            or self.item.confidence != self.derivation.confidence
            or self.item.evidence_status is not self.derivation.evidence_status
        ):
            raise ValueError("transcription item projection is inconsistent")

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.models import IngestionWarning
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.configuration.configuration import (
    TranscriptionConfiguration,
)
from projectkoios.ingestion.transcription.configuration.error import (
    TranscriptionLimitError,
)
from projectkoios.ingestion.transcription.item.item import TranscriptionItem
from projectkoios.ingestion.transcription.omission.omission import (
    TranscriptionOmission,
)


@dataclass(frozen=True)
class TranscriptionResultLimitValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    result_id: str
    items: tuple[TranscriptionItem, ...]
    omissions: tuple[TranscriptionOmission, ...]
    warnings: tuple[IngestionWarning, ...]
    configuration: TranscriptionConfiguration
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported transcription limit validation version"
            )
        self.validate_identity_fields(self.result_id)
        if len(self.items) > self.configuration.max_items:
            raise TranscriptionLimitError("items exceed max_items")
        if len(self.omissions) > self.configuration.max_omissions:
            raise TranscriptionLimitError("omissions exceed max_omissions")
        if len(self.warnings) > self.configuration.max_warnings:
            raise TranscriptionLimitError("warnings exceed max_warnings")
        total_spans = sum(len(item.source_spans) for item in self.items) + sum(
            len(item.source_spans) for item in self.omissions
        )
        if total_spans > self.configuration.max_source_spans:
            raise TranscriptionLimitError(
                "source spans exceed max_source_spans"
            )
        text_lengths = tuple(
            len(item.normalized_text or "")
            + sum(len(text) for text in item.source_texts)
            for item in self.items
        )
        if any(
            length > self.configuration.max_text_characters_per_item
            for length in text_lengths
        ):
            raise TranscriptionLimitError(
                "item text exceeds max_text_characters_per_item"
            )
        if sum(text_lengths) > self.configuration.max_total_text_characters:
            raise TranscriptionLimitError(
                "text exceeds max_total_text_characters"
            )
        self.validate_retained_size(
            (self.items, self.omissions, self.warnings),
            self.configuration.max_result_bytes,
        )

    @property
    def validated_item_count(self) -> int:
        return len(self.items)

    @property
    def validated_source_span_count(self) -> int:
        return sum(len(item.source_spans) for item in self.items) + sum(
            len(item.source_spans) for item in self.omissions
        )

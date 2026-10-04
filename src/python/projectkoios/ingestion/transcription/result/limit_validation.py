from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.configuration.configuration import (  # noqa: E501
    TranscriptionConfiguration,
)
from projectkoios.ingestion.transcription.limit_error import (
    TranscriptionLimitError,
)
from projectkoios.ingestion.transcription.result.result import (
    StructuredTranscriptionResult,
)


@dataclass(frozen=True)
class TranscriptionResultLimitValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    result_id: str
    validated_item_count: int
    validated_source_span_count: int
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        result: StructuredTranscriptionResult,
        configuration: TranscriptionConfiguration,
    ) -> TranscriptionResultLimitValidation:
        cls._validate_configured_result(result, configuration)
        return cls(
            result.result_id,
            len(result.items),
            sum(len(item.source_spans) for item in result.items)
            + sum(len(item.source_spans) for item in result.omissions),
        )

    @staticmethod
    def _validate_configured_result(
        result: StructuredTranscriptionResult,
        configuration: TranscriptionConfiguration,
    ) -> None:
        if len(result.items) > configuration.max_items:
            raise TranscriptionLimitError("items exceed max_items")
        if len(result.omissions) > configuration.max_omissions:
            raise TranscriptionLimitError("omissions exceed max_omissions")
        if len(result.warnings) > configuration.max_warnings:
            raise TranscriptionLimitError("warnings exceed max_warnings")
        total_spans = sum(
            len(item.source_spans) for item in result.items
        ) + sum(len(item.source_spans) for item in result.omissions)
        if total_spans > configuration.max_source_spans:
            raise TranscriptionLimitError(
                "source spans exceed max_source_spans"
            )
        text_lengths = tuple(
            len(item.normalized_text or "")
            + sum(len(text) for text in item.source_texts)
            for item in result.items
        )
        if any(
            length > configuration.max_text_characters_per_item
            for length in text_lengths
        ):
            raise TranscriptionLimitError(
                "item text exceeds max_text_characters_per_item"
            )
        if sum(text_lengths) > configuration.max_total_text_characters:
            raise TranscriptionLimitError(
                "text exceeds max_total_text_characters"
            )
        AbstractTranscriptionDataObject._validate_retained_size(
            result, configuration.max_result_bytes
        )

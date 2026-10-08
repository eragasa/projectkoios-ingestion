"""Immutable current structured-item production requests."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.inventory import (  # noqa: E501
    ReadingPageTextProducerEvidenceInventory,
)
from projectkoios.ingestion.transcription.result.structured import (
    StructuredTranscriptionResult,
)


@dataclass(frozen=True, slots=True)
class ReadingStructuredItemProductionRequest(DataObjectActionRequest):
    """Bind one current transcription to exact page-text evidence."""

    transcription: StructuredTranscriptionResult
    page_text: ReadingPageTextProducerEvidenceInventory

    def __post_init__(self) -> None:
        if type(self.transcription) is not StructuredTranscriptionResult:
            raise TypeError(
                "transcription must be StructuredTranscriptionResult"
            )
        if type(self.page_text) is not ReadingPageTextProducerEvidenceInventory:
            raise TypeError(
                "page_text must be ReadingPageTextProducerEvidenceInventory"
            )
        source_pages = self.transcription.transcription_input.document.pages
        target_pages = tuple(self.page_text)
        if len(source_pages) != len(target_pages):
            raise ReadingEvidenceError(
                "structured transcription and page text require equal coverage"
            )
        for source_page, target_page in zip(
            source_pages, target_pages, strict=True
        ):
            location = target_page.streams.page_location
            if (
                source_page.page_index != location.physical_page_index
                or source_page.printed_page_label != location.printed_page_label
            ):
                raise ReadingEvidenceError(
                    "structured transcription location differs from page text"
                )

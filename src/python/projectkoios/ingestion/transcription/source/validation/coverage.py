from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.item.item import TranscriptionItem
from projectkoios.ingestion.transcription.item.kind import TranscriptionItemKind
from projectkoios.ingestion.transcription.request.request import (
    StructuredTranscriptionRequest,
)
from projectkoios.ingestion.transcription.source.object_kind import (
    TranscriptionSourceObjectKind,
)


@dataclass(frozen=True)
class TranscriptionSourceCoverageValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    transcription_input: StructuredTranscriptionRequest
    items: tuple[TranscriptionItem, ...]
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported source coverage validation version")
        page_anchor_indices = tuple(
            item.page_index
            for item in self.items
            if item.item_kind is TranscriptionItemKind.PAGE_ANCHOR
        )
        expected_page_indices = tuple(
            page.page_index for page in self.transcription_input.document.pages
        )
        if page_anchor_indices != expected_page_indices:
            raise ValueError("transcription page anchors are incomplete")
        table_result = self.transcription_input.table_structure_result
        for source_kind, expected_ids in (
            (
                TranscriptionSourceObjectKind.EQUATION_CANDIDATE,
                {
                    candidate.candidate_id
                    for candidate in (
                        self.transcription_input.equation_detection_result.candidates
                    )
                },
            ),
            (
                TranscriptionSourceObjectKind.TABLE_STRUCTURE,
                {
                    structure.structure_id
                    for structure in table_result.structures
                },
            ),
            (
                TranscriptionSourceObjectKind.FIGURE_CANDIDATE,
                {
                    candidate.candidate_id
                    for candidate in (
                        self.transcription_input.figure_detection_result.candidates
                    )
                },
            ),
        ):
            actual_ids = {
                item.source_object_id
                for item in self.items
                if item.source_object_kind is source_kind
            }
            if actual_ids != expected_ids:
                raise ValueError(
                    "transcription typed-object coverage is incomplete"
                )

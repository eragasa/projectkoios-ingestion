from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractDerivation
from projectkoios.ingestion.models import Metadata, SourceSpan
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.evidence.status import (
    TranscriptionEvidenceStatus,
)
from projectkoios.ingestion.transcription.item.item import TranscriptionItem
from projectkoios.ingestion.transcription.item.kind import TranscriptionItemKind
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
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported transcription derivation version")
        if not isinstance(self.item_kind, TranscriptionItemKind):
            raise TypeError("transcription derivation item kind is unsupported")
        if not isinstance(
            self.source_object_kind, TranscriptionSourceObjectKind
        ):
            raise TypeError(
                "transcription derivation source kind is unsupported"
            )
        self.validate_identity_fields(self.source_object_id)
        self.validate_nonnegative_integer(
            "derivation page index", self.page_index
        )
        if self.printed_page_label is not None:
            self.validate_bounded_string(
                "printed page label", self.printed_page_label
            )
        self.validate_unique_strings(
            "derivation source block IDs", self.source_block_ids
        )
        self.validate_source_spans(self.source_spans)
        self.validate_tuple("derivation source texts", self.source_texts)
        for text in self.source_texts:
            self.validate_bounded_string(
                "derivation source text",
                text,
                limit=self.MAX_TEXT_CHARACTERS_PER_ITEM,
            )
        if not isinstance(self.evidence_status, TranscriptionEvidenceStatus):
            raise TypeError(
                "transcription derivation evidence status is unsupported"
            )
        if self.confidence is not None:
            object.__setattr__(
                self,
                "confidence",
                self.validate_unit_float(
                    "derivation confidence", self.confidence
                ),
            )
        if self.structure_reading_order is not None:
            self.validate_nonnegative_integer(
                "structure reading order", self.structure_reading_order
            )
        self.validate_metadata(self.evidence)
        self.validate_unique_strings(
            "derivation warning codes", self.warning_codes
        )

    @property
    def item_id(self) -> str:
        normalized = (
            self.normalize_text(self.source_texts)
            if self.source_texts
            else None
        )
        method = self.NORMALIZATION_METHOD if self.source_texts else None
        return TranscriptionItem.identity_for(
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

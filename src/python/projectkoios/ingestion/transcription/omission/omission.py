from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    Metadata,
    SourceSpan,
)
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.omission_reason import (
    TranscriptionOmissionReason,
)


@dataclass(frozen=True)
class TranscriptionOmission(AbstractTranscriptionDataObject):
    omission_id: str
    omitted_object_id: str
    source_block_id: str
    source_spans: tuple[SourceSpan, ...]
    reason: TranscriptionOmissionReason
    represented_by_item_ids: tuple[str, ...]
    warning_ids: tuple[str, ...] = ()
    evidence: Metadata = ()
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        omitted_object_id: str,
        source_block_id: str,
        source_spans: tuple[SourceSpan, ...],
        reason: TranscriptionOmissionReason,
        represented_by_item_ids: tuple[str, ...] = (),
        warning_ids: tuple[str, ...] = (),
        evidence: Metadata = (),
    ) -> TranscriptionOmission:
        return cls(
            omission_id=TranscriptionOmission._omission_id(
                omitted_object_id,
                source_block_id,
                source_spans,
                reason,
                represented_by_item_ids,
                evidence,
            ),
            omitted_object_id=omitted_object_id,
            source_block_id=source_block_id,
            source_spans=source_spans,
            reason=reason,
            represented_by_item_ids=represented_by_item_ids,
            warning_ids=warning_ids,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != AbstractTranscriptionDataObject.CONTRACT_VERSION
        ):
            raise ValueError("unsupported transcription omission version")
        AbstractTranscriptionDataObject._identity_fields(
            self.omitted_object_id, self.source_block_id
        )
        AbstractTranscriptionDataObject._validate_spans(self.source_spans)
        if not isinstance(self.reason, TranscriptionOmissionReason):
            raise TypeError("transcription omission reason is unsupported")
        AbstractTranscriptionDataObject._unique_strings(
            "represented item IDs", self.represented_by_item_ids
        )
        AbstractTranscriptionDataObject._unique_strings(
            "omission warning IDs", self.warning_ids
        )
        AbstractTranscriptionDataObject._validate_metadata(self.evidence)
        represented_reason = self.reason in (
            TranscriptionOmissionReason.REPRESENTED_BY_TYPED_OBJECT,
            TranscriptionOmissionReason.REPRESENTED_BY_EARLIER_ITEM,
        )
        if represented_reason != bool(self.represented_by_item_ids):
            raise ValueError("omission representation links are inconsistent")
        expected = TranscriptionOmission._omission_id(
            self.omitted_object_id,
            self.source_block_id,
            self.source_spans,
            self.reason,
            self.represented_by_item_ids,
            self.evidence,
        )
        if self.omission_id != expected:
            raise ValueError("transcription omission ID is inconsistent")

    @staticmethod
    def _omission_id(
        omitted_object_id: str,
        source_block_id: str,
        source_spans: tuple[SourceSpan, ...],
        reason: TranscriptionOmissionReason,
        represented_by_item_ids: tuple[str, ...],
        evidence: Metadata,
    ) -> str:
        return stable_id(
            "structured-transcription-omission",
            omitted_object_id,
            source_block_id,
            tuple(
                AbstractTranscriptionDataObject._span_parts(span)
                for span in source_spans
            ),
            reason.value,
            represented_by_item_ids,
            evidence,
        )

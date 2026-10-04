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
from projectkoios.ingestion.transcription.evidence.status import (
    TranscriptionEvidenceStatus,
)
from projectkoios.ingestion.transcription.item.kind import (
    TranscriptionItemKind,
)
from projectkoios.ingestion.transcription.order.status import (
    TranscriptionOrderStatus,
)
from projectkoios.ingestion.transcription.source.object_kind import (
    TranscriptionSourceObjectKind,
)


@dataclass(frozen=True)
class TranscriptionItem(AbstractTranscriptionDataObject):
    item_id: str
    item_kind: TranscriptionItemKind
    source_object_kind: TranscriptionSourceObjectKind
    source_object_id: str
    page_index: int
    printed_page_label: str | None
    order_index: int
    order_status: TranscriptionOrderStatus
    evidence_status: TranscriptionEvidenceStatus
    confidence: float | None
    source_block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    normalized_text: str | None
    source_texts: tuple[str, ...]
    normalization_method: str | None
    warning_ids: tuple[str, ...] = ()
    evidence: Metadata = ()
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        item_kind: TranscriptionItemKind,
        source_object_kind: TranscriptionSourceObjectKind,
        source_object_id: str,
        page_index: int,
        printed_page_label: str | None,
        order_index: int,
        order_status: TranscriptionOrderStatus,
        evidence_status: TranscriptionEvidenceStatus,
        confidence: float | None,
        source_block_ids: tuple[str, ...],
        source_spans: tuple[SourceSpan, ...],
        source_texts: tuple[str, ...] = (),
        warning_ids: tuple[str, ...] = (),
        evidence: Metadata = (),
    ) -> TranscriptionItem:
        normalized_text = (
            AbstractTranscriptionDataObject.normalize_text(source_texts)
            if source_texts
            else None
        )
        method = (
            AbstractTranscriptionDataObject.NORMALIZATION_METHOD
            if source_texts
            else None
        )
        return cls(
            item_id=TranscriptionItem.identity_for(
                item_kind,
                source_object_kind,
                source_object_id,
                page_index,
                source_block_ids,
                source_spans,
                normalized_text,
                source_texts,
                method,
                evidence_status,
                confidence,
                evidence,
            ),
            item_kind=item_kind,
            source_object_kind=source_object_kind,
            source_object_id=source_object_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            order_index=order_index,
            order_status=order_status,
            evidence_status=evidence_status,
            confidence=confidence,
            source_block_ids=source_block_ids,
            source_spans=source_spans,
            normalized_text=normalized_text,
            source_texts=source_texts,
            normalization_method=method,
            warning_ids=warning_ids,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != AbstractTranscriptionDataObject.CONTRACT_VERSION
        ):
            raise ValueError("unsupported transcription item version")
        if not isinstance(self.item_kind, TranscriptionItemKind):
            raise TypeError("transcription item kind is unsupported")
        if not isinstance(
            self.source_object_kind, TranscriptionSourceObjectKind
        ):
            raise TypeError("transcription source-object kind is unsupported")
        AbstractTranscriptionDataObject.validate_identity_fields(
            self.source_object_id
        )
        AbstractTranscriptionDataObject.validate_nonnegative_integer(
            "item page index", self.page_index
        )
        AbstractTranscriptionDataObject.validate_nonnegative_integer(
            "item order index", self.order_index
        )
        if self.printed_page_label is not None:
            AbstractTranscriptionDataObject.validate_bounded_string(
                "printed page label", self.printed_page_label
            )
        if not isinstance(self.order_status, TranscriptionOrderStatus):
            raise TypeError("transcription order status is unsupported")
        if not isinstance(self.evidence_status, TranscriptionEvidenceStatus):
            raise TypeError("transcription evidence status is unsupported")
        if self.confidence is not None:
            object.__setattr__(
                self,
                "confidence",
                AbstractTranscriptionDataObject.validate_unit_float(
                    "item confidence", self.confidence
                ),
            )
        AbstractTranscriptionDataObject.validate_unique_strings(
            "item source block IDs", self.source_block_ids
        )
        AbstractTranscriptionDataObject.validate_source_spans(self.source_spans)
        AbstractTranscriptionDataObject.validate_tuple(
            "source texts", self.source_texts
        )
        for text in self.source_texts:
            AbstractTranscriptionDataObject.validate_bounded_string(
                "source text",
                text,
                limit=AbstractTranscriptionDataObject.MAX_TEXT_CHARACTERS_PER_ITEM,
            )
        if self.source_texts:
            if (
                self.normalization_method
                != AbstractTranscriptionDataObject.NORMALIZATION_METHOD
            ):
                raise ValueError(
                    "text item normalization method is inconsistent"
                )
            if (
                self.normalized_text
                != AbstractTranscriptionDataObject.normalize_text(
                    self.source_texts
                )
            ):
                raise ValueError("normalized text is inconsistent")
            assert self.normalized_text is not None
            AbstractTranscriptionDataObject.validate_bounded_string(
                "normalized text",
                self.normalized_text,
                limit=AbstractTranscriptionDataObject.MAX_TEXT_CHARACTERS_PER_ITEM,
            )
        elif (
            self.normalized_text is not None
            or self.normalization_method is not None
        ):
            raise ValueError("text-free item cannot contain normalized text")
        AbstractTranscriptionDataObject.validate_unique_strings(
            "item warning IDs", self.warning_ids
        )
        AbstractTranscriptionDataObject.validate_metadata(self.evidence)
        expected = TranscriptionItem.identity_for(
            self.item_kind,
            self.source_object_kind,
            self.source_object_id,
            self.page_index,
            self.source_block_ids,
            self.source_spans,
            self.normalized_text,
            self.source_texts,
            self.normalization_method,
            self.evidence_status,
            self.confidence,
            self.evidence,
        )
        if self.item_id != expected:
            raise ValueError("transcription item ID is inconsistent")

    @classmethod
    def identity_for(
        cls,
        item_kind: TranscriptionItemKind,
        source_object_kind: TranscriptionSourceObjectKind,
        source_object_id: str,
        page_index: int,
        source_block_ids: tuple[str, ...],
        source_spans: tuple[SourceSpan, ...],
        normalized_text: str | None,
        source_texts: tuple[str, ...],
        normalization_method: str | None,
        evidence_status: TranscriptionEvidenceStatus,
        confidence: float | None,
        evidence: Metadata,
    ) -> str:
        return stable_id(
            "structured-transcription-item",
            item_kind.value,
            source_object_kind.value,
            source_object_id,
            page_index,
            source_block_ids,
            tuple(
                AbstractTranscriptionDataObject.source_span_identity_parts(span)
                for span in source_spans
            ),
            normalized_text,
            source_texts,
            normalization_method,
            evidence_status.value,
            confidence,
            evidence,
        )

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import ExtractedDocument, ExtractedPage
from projectkoios.ingestion.transcription.derivation.model import (
    TranscriptionDerivation,
)
from projectkoios.ingestion.transcription.kind.item import TranscriptionItemKind
from projectkoios.ingestion.transcription.kind.source.object import (
    TranscriptionSourceObjectKind,
)
from projectkoios.ingestion.transcription.status.evidence import (
    TranscriptionEvidenceStatus,
)


@dataclass(frozen=True)
class PageTranscriptionDerivation(TranscriptionDerivation):
    @classmethod
    def derive(
        cls, document: ExtractedDocument, page: ExtractedPage
    ) -> PageTranscriptionDerivation:
        return cls(
            item_kind=TranscriptionItemKind.PAGE_ANCHOR,
            source_object_kind=TranscriptionSourceObjectKind.PAGE,
            source_object_id=cls.source_object_identity(document, page),
            page_index=page.page_index,
            printed_page_label=page.printed_page_label,
            source_block_ids=(),
            source_spans=(),
            source_texts=(),
            evidence_status=TranscriptionEvidenceStatus.OBSERVED_SOURCE_TRANSFORM,
            confidence=None,
            structure_reading_order=None,
            evidence=(("page_index", str(page.page_index)),),
        )

    @classmethod
    def source_object_identity(
        cls, document: ExtractedDocument, page: ExtractedPage
    ) -> str:
        return stable_id(
            "transcription-page-anchor",
            document.source.source_id,
            document.source.blob_id,
            page.page_index,
        )

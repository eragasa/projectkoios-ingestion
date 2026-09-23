from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import BaseDocument
from projectkoios.ingestion.documents.pdf.models import PdfProcessedDocument
from projectkoios.ingestion.layout import PageLayoutResult


@dataclass(frozen=True)
class PilotDocument(BaseDocument):
    pass


@dataclass(frozen=True)
class PilotDeterministicProcessedDocument(PdfProcessedDocument):
    """Verified PDF extraction plus the completed deterministic prefix."""

    page_layouts: tuple[PageLayoutResult, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.extraction is None:
            raise ValueError(
                "deterministic processing requires retained extraction evidence"
            )
        if not isinstance(self.page_layouts, tuple) or any(
            not isinstance(layout, PageLayoutResult)
            for layout in self.page_layouts
        ):
            raise TypeError("page_layouts must be a tuple of PageLayoutResult")
        extracted_pages = self.extraction.document.pages
        if tuple(layout.page_index for layout in self.page_layouts) != tuple(
            page.page_index for page in extracted_pages
        ):
            raise ValueError(
                "page layouts must correspond to every extracted page in order"
            )
        source = self.extraction.document.source
        if any(
            layout.source_id != source.source_id
            or layout.source_blob_id != source.blob_id
            or layout.source_content_hash != source.content_hash
            for layout in self.page_layouts
        ):
            raise ValueError(
                "page layouts must retain the exact extraction source identity"
            )


__all__ = ["PilotDeterministicProcessedDocument", "PilotDocument"]

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from projectkoios.ingestion.base import (
    BaseDocument,
    BaseDocumentProcessor,
    BaseProcessedDocument,
)
from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.pdf import PyMuPdfExtractor


@dataclass(frozen=True)
class PdfProcessedPage:
    page_index: int
    page_label: str | None
    text: str


@dataclass(frozen=True)
class PdfProcessedDocument(BaseProcessedDocument):
    pages: tuple[PdfProcessedPage, ...]


class PdfDocumentProcessor(BaseDocumentProcessor):
    name = "pdf-document-processor"
    version = "0"

    def __init__(self, extractor: PyMuPdfExtractor | None = None) -> None:
        self.extractor = extractor or PyMuPdfExtractor()

    def process(self, document: BaseDocument) -> PdfProcessedDocument:
        if document.media_type != "application/pdf":
            raise ValueError("PdfDocumentProcessor requires application/pdf")

        source = SourceDocument.from_bytes(
            document.content,
            source_id=document.source_id.citation_key,
            media_type=document.media_type,
            locator=document.locator,
        )
        extraction = self.extractor.extract(
            source,
            BytesIO(document.content),
        )
        pages = tuple(
            PdfProcessedPage(
                page_index=page.page_index,
                page_label=page.printed_page_label,
                text="\n".join(
                    block.text
                    for block in page.blocks
                    if block.kind == "text" and block.text
                ),
            )
            for page in extraction.document.pages
        )
        return PdfProcessedDocument(source=document, pages=pages)


__all__ = [
    "PdfDocumentProcessor",
    "PdfProcessedDocument",
    "PdfProcessedPage",
]

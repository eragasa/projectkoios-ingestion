from __future__ import annotations

from io import BytesIO

from projectkoios.ingestion.base import BaseDocument, BaseDocumentProcessor
from projectkoios.ingestion.documents.pdf.models import PdfProcessedDocument
from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.pdf import PyMuPdfExtractor


class PdfDocumentProcessor(BaseDocumentProcessor):
    name = "pdf-document-processor"
    version = "1"

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
        return PdfProcessedDocument(
            source=document,
            pages=PdfProcessedDocument.pages_from_extraction(extraction),
            extraction=extraction,
        )


__all__ = ["PdfDocumentProcessor"]

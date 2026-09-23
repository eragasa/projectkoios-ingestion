from __future__ import annotations

from pathlib import Path

from projectkoios.ingestion.base import BaseDocument
from projectkoios.ingestion.bibtex import BibtexParser
from projectkoios.ingestion.cache import deserialize_extraction_result
from projectkoios.ingestion.documents.pdf.deserialization import (
    BaseProcessedDocumentDeserializer,
)
from projectkoios.ingestion.documents.pdf.errors import (
    ProcessedPdfDocumentDeserializationError,
)
from projectkoios.ingestion.documents.pdf.models import PdfProcessedDocument
from projectkoios.ingestion.models import SourceDocument

_MAX_BIBTEX_BYTES = 10_000_000
_MAX_PDF_BYTES = 512_000_000
_MAX_PROCESSED_DOCUMENT_BYTES = 512_000_000


class ProcessedPdfDocumentDeserializer(
    BaseProcessedDocumentDeserializer[PdfProcessedDocument]
):
    """Load one PDF projection from explicit BibTeX, PDF, and artifact paths."""

    name = "pdf-processed-document-deserializer"
    version = "1"

    def __init__(
        self,
        *,
        max_bibtex_bytes: int = _MAX_BIBTEX_BYTES,
        max_pdf_bytes: int = _MAX_PDF_BYTES,
        max_processed_document_bytes: int = _MAX_PROCESSED_DOCUMENT_BYTES,
    ) -> None:
        self.max_bibtex_bytes = self._positive_limit(
            max_bibtex_bytes,
            "max_bibtex_bytes",
        )
        self.max_pdf_bytes = self._positive_limit(
            max_pdf_bytes,
            "max_pdf_bytes",
        )
        self.max_processed_document_bytes = self._positive_limit(
            max_processed_document_bytes,
            "max_processed_document_bytes",
        )

    def deserialize(
        self,
        *,
        citation_key: str,
        bibtex_path: Path,
        pdf_path: Path,
        processed_document_path: Path,
    ) -> PdfProcessedDocument:
        try:
            bibtex_bytes = self._read_regular_file(
                bibtex_path,
                limit=self.max_bibtex_bytes,
                label="BibTeX source",
            )
            bibtex_text = bibtex_bytes.decode("utf-8", errors="strict")
            record = BibtexParser().parse(bibtex_text, citation_key)
            pdf = self._read_regular_file(
                pdf_path,
                limit=self.max_pdf_bytes,
                label="PDF source",
            )
            if not pdf.startswith(b"%PDF-"):
                raise ValueError("PDF source does not have a PDF header")
            extraction_bytes = self._read_regular_file(
                processed_document_path,
                limit=self.max_processed_document_bytes,
                label="processed document",
            )
            extraction_text = extraction_bytes.decode(
                "utf-8",
                errors="strict",
            )
            extraction = deserialize_extraction_result(extraction_text)
            extracted_source = extraction.document.source
            expected_source = SourceDocument.from_bytes(
                pdf,
                source_id=citation_key,
                media_type="application/pdf",
                locator=extracted_source.locator,
            )
            if extracted_source != expected_source:
                raise ValueError(
                    "processed document does not match the exact PDF source"
                )
            source = BaseDocument(
                source_id=record,
                locator=extracted_source.locator,
                media_type=extracted_source.media_type,
                content=pdf,
            )
            return PdfProcessedDocument(
                source=source,
                pages=PdfProcessedDocument.pages_from_extraction(extraction),
                extraction=extraction,
            )
        except ProcessedPdfDocumentDeserializationError:
            raise
        except (
            OSError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
        ) as error:
            raise ProcessedPdfDocumentDeserializationError(
                f"cannot deserialize {citation_key!r}: {error}"
            ) from error


class ProcessedPdfDocument:
    """Facade that encapsulates one concrete PDF document deserializer."""

    def __init__(
        self,
        deserializer: ProcessedPdfDocumentDeserializer | None = None,
    ) -> None:
        self._deserializer = deserializer or ProcessedPdfDocumentDeserializer()

    @property
    def deserializer(self) -> ProcessedPdfDocumentDeserializer:
        return self._deserializer

    def deserialize(
        self,
        *,
        citation_key: str,
        bibtex_path: Path,
        pdf_path: Path,
        processed_document_path: Path,
    ) -> PdfProcessedDocument:
        return self._deserializer.deserialize(
            citation_key=citation_key,
            bibtex_path=bibtex_path,
            pdf_path=pdf_path,
            processed_document_path=processed_document_path,
        )


__all__ = [
    "ProcessedPdfDocument",
    "ProcessedPdfDocumentDeserializer",
]

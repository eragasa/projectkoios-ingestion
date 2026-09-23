from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from projectkoios.ingestion.base import (
    BaseProcessedDocument,
    BaseProcessedPage,
)
from projectkoios.ingestion.models import ExtractionResult, SourceDocument

PROCESSED_PDF_DOCUMENTS_SCHEMA_VERSION = 1
MAX_CORPUS_DOCUMENTS = 256
MAX_IDENTITY_CHARACTERS = 4096


@dataclass(frozen=True)
class ProcessedPdfPage(BaseProcessedPage):
    page_label: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.page_label is not None and not isinstance(self.page_label, str):
            raise TypeError("page_label must be a string or None")


@dataclass(frozen=True)
class PdfProcessedDocument(BaseProcessedDocument):
    pages: tuple[ProcessedPdfPage, ...]
    extraction: ExtractionResult | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.pages, tuple) or any(
            not isinstance(page, ProcessedPdfPage) for page in self.pages
        ):
            raise TypeError("pages must be a tuple of ProcessedPdfPage values")
        indices = tuple(page.page_index for page in self.pages)
        if indices != tuple(sorted(set(indices))):
            raise ValueError(
                "processed pages must have unique ascending indices"
            )
        if self.extraction is None:
            return
        if not isinstance(self.extraction, ExtractionResult):
            raise TypeError("extraction must be an ExtractionResult or None")
        source = SourceDocument.from_bytes(
            self.source.content,
            source_id=self.source.source_id.citation_key,
            media_type=self.source.media_type,
            locator=self.source.locator,
        )
        if self.extraction.document.source != source:
            raise ValueError(
                "processed document source does not match its extraction"
            )
        if self.pages != self.pages_from_extraction(self.extraction):
            raise ValueError(
                "processed document pages do not match its extraction"
            )

    @staticmethod
    def pages_from_extraction(
        extraction: ExtractionResult,
    ) -> tuple[ProcessedPdfPage, ...]:
        return tuple(
            ProcessedPdfPage(
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


@dataclass(frozen=True)
class PdfProcessedDocuments:
    documents: tuple[PdfProcessedDocument, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.documents, tuple) or not self.documents:
            raise ValueError(
                "PdfProcessedDocuments must contain a non-empty tuple"
            )
        if len(self.documents) > MAX_CORPUS_DOCUMENTS:
            raise ValueError("PdfProcessedDocuments exceeds the item limit")
        if any(
            not isinstance(document, PdfProcessedDocument)
            for document in self.documents
        ):
            raise TypeError(
                "documents must contain only PdfProcessedDocument values"
            )
        citation_keys = tuple(
            document.source.source_id.citation_key
            for document in self.documents
        )
        if len(citation_keys) != len(set(citation_keys)):
            raise ValueError(
                "PdfProcessedDocuments contains duplicate citation keys"
            )


@dataclass(frozen=True)
class ProcessedPdfDocumentLocation:
    citation_key: str
    bibtex_path: PurePosixPath
    pdf_path: PurePosixPath
    processed_document_path: PurePosixPath

    def __post_init__(self) -> None:
        if (
            not isinstance(self.citation_key, str)
            or not self.citation_key
            or len(self.citation_key) > MAX_IDENTITY_CHARACTERS
        ):
            raise ValueError("citation_key must be a bounded non-empty string")
        for name, value in (
            ("bibtex_path", self.bibtex_path),
            ("pdf_path", self.pdf_path),
            ("processed_document_path", self.processed_document_path),
        ):
            self._validate_relative_path(value, name)
        if self.bibtex_path.suffix.lower() not in {".bib", ".bibtex"}:
            raise ValueError("bibtex_path must name a .bib or .bibtex file")
        if self.pdf_path.suffix.lower() != ".pdf":
            raise ValueError("pdf_path must name a .pdf file")
        if self.processed_document_path.suffix.lower() != ".json":
            raise ValueError("processed_document_path must name a .json file")

    @classmethod
    def from_dict(cls, value: object) -> ProcessedPdfDocumentLocation:
        if not isinstance(value, dict):
            raise ValueError("processed-document location must be an object")
        expected = {
            "citation_key",
            "bibtex_path",
            "pdf_path",
            "processed_document_path",
        }
        if set(value) != expected:
            missing = sorted(expected - set(value))
            extra = sorted(set(value) - expected)
            raise ValueError(
                "processed-document location fields are invalid: "
                f"missing={missing}, extra={extra}"
            )
        citation_key = value["citation_key"]
        if not isinstance(citation_key, str):
            raise ValueError("citation_key must be a string")
        return cls(
            citation_key=citation_key,
            bibtex_path=cls._relative_path(
                value["bibtex_path"],
                "bibtex_path",
            ),
            pdf_path=cls._relative_path(value["pdf_path"], "pdf_path"),
            processed_document_path=cls._relative_path(
                value["processed_document_path"],
                "processed_document_path",
            ),
        )

    @staticmethod
    def _validate_relative_path(value: PurePosixPath, field: str) -> None:
        if not isinstance(value, PurePosixPath):
            raise TypeError(f"{field} must be a PurePosixPath")
        if (
            value.is_absolute()
            or not value.parts
            or ".." in value.parts
            or any(part in {"", "."} for part in value.parts)
        ):
            raise ValueError(f"{field} must be a safe relative path")

    @classmethod
    def _relative_path(
        cls,
        value: object,
        field: str,
    ) -> PurePosixPath:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} must be a non-empty string")
        if len(value) > MAX_IDENTITY_CHARACTERS:
            raise ValueError(f"{field} is too long")
        path = PurePosixPath(value)
        cls._validate_relative_path(path, field)
        if path.as_posix() != value:
            raise ValueError(f"{field} must be normalized")
        return path


__all__ = [
    "MAX_CORPUS_DOCUMENTS",
    "PROCESSED_PDF_DOCUMENTS_SCHEMA_VERSION",
    "PdfProcessedDocument",
    "PdfProcessedDocuments",
    "ProcessedPdfDocumentLocation",
    "ProcessedPdfPage",
]

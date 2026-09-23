from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

from projectkoios.ingestion.base import (
    BaseDocument,
    BaseDocumentProcessor,
    BaseProcessedDocument,
    BaseProcessedPage,
)
from projectkoios.ingestion.bibtex import BibtexParser
from projectkoios.ingestion.cache import deserialize_extraction_result
from projectkoios.ingestion.models import ExtractionResult, SourceDocument
from projectkoios.ingestion.pdf import PyMuPdfExtractor

PROCESSED_PDF_DOCUMENTS_SCHEMA_VERSION = 1
_MAX_CORPUS_DOCUMENTS = 256
_MAX_MANIFEST_BYTES = 5_000_000
_MAX_BIBTEX_BYTES = 10_000_000
_MAX_PDF_BYTES = 512_000_000
_MAX_PROCESSED_DOCUMENT_BYTES = 512_000_000
_MAX_IDENTITY_CHARACTERS = 4096


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
        if self.pages != _project_pages(self.extraction):
            raise ValueError(
                "processed document pages do not match its extraction"
            )


@dataclass(frozen=True)
class PdfProcessedDocuments:
    documents: tuple[PdfProcessedDocument, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.documents, tuple) or not self.documents:
            raise ValueError(
                "PdfProcessedDocuments must contain a non-empty tuple"
            )
        if len(self.documents) > _MAX_CORPUS_DOCUMENTS:
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
            or len(self.citation_key) > _MAX_IDENTITY_CHARACTERS
        ):
            raise ValueError("citation_key must be a bounded non-empty string")
        for name, value in (
            ("bibtex_path", self.bibtex_path),
            ("pdf_path", self.pdf_path),
            ("processed_document_path", self.processed_document_path),
        ):
            _validate_relative_path(value, name)
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
            bibtex_path=_relative_path(value["bibtex_path"], "bibtex_path"),
            pdf_path=_relative_path(value["pdf_path"], "pdf_path"),
            processed_document_path=_relative_path(
                value["processed_document_path"],
                "processed_document_path",
            ),
        )


class ProcessedPdfDocumentDeserializationError(ValueError):
    """Raised when one location triple cannot produce a verified document."""


class ProcessedPdfDocumentDeserializer:
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
        self.max_bibtex_bytes = _positive_limit(
            max_bibtex_bytes, "max_bibtex_bytes"
        )
        self.max_pdf_bytes = _positive_limit(max_pdf_bytes, "max_pdf_bytes")
        self.max_processed_document_bytes = _positive_limit(
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
            bibtex_bytes = _read_regular_file(
                bibtex_path,
                limit=self.max_bibtex_bytes,
                label="BibTeX source",
            )
            bibtex_text = bibtex_bytes.decode("utf-8", errors="strict")
            record = BibtexParser().parse(bibtex_text, citation_key)
            pdf = _read_regular_file(
                pdf_path,
                limit=self.max_pdf_bytes,
                label="PDF source",
            )
            if not pdf.startswith(b"%PDF-"):
                raise ValueError("PDF source does not have a PDF header")
            extraction_bytes = _read_regular_file(
                processed_document_path,
                limit=self.max_processed_document_bytes,
                label="processed document",
            )
            extraction_text = extraction_bytes.decode("utf-8", errors="strict")
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
                pages=_project_pages(extraction),
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


class ProcessedPdfDocumentsDeserializer:
    """Load an ordered corpus from one explicit path manifest."""

    name = "pdf-processed-documents-deserializer"
    version = "1"

    def __init__(
        self,
        document_deserializer: ProcessedPdfDocumentDeserializer | None = None,
        *,
        max_manifest_bytes: int = _MAX_MANIFEST_BYTES,
        max_documents: int = _MAX_CORPUS_DOCUMENTS,
    ) -> None:
        self.document_deserializer = (
            document_deserializer or ProcessedPdfDocumentDeserializer()
        )
        self.max_manifest_bytes = _positive_limit(
            max_manifest_bytes, "max_manifest_bytes"
        )
        self.max_documents = _positive_limit(max_documents, "max_documents")
        if self.max_documents > _MAX_CORPUS_DOCUMENTS:
            raise ValueError(
                f"max_documents cannot exceed {_MAX_CORPUS_DOCUMENTS}"
            )

    def deserialize(self, manifest_path: Path) -> PdfProcessedDocuments:
        try:
            manifest = manifest_path.expanduser().absolute()
            manifest_bytes = _read_regular_file(
                manifest,
                limit=self.max_manifest_bytes,
                label="processed-documents manifest",
            )
            value = json.loads(
                manifest_bytes.decode("utf-8", errors="strict"),
                object_pairs_hook=_object_without_duplicates,
                parse_constant=_reject_json_constant,
            )
            locations = _manifest_locations(value, self.max_documents)
            root = manifest.parent.resolve(strict=True)
            documents = tuple(
                self.document_deserializer.deserialize(
                    citation_key=location.citation_key,
                    bibtex_path=_resolve_location(
                        root, location.bibtex_path, "bibtex_path"
                    ),
                    pdf_path=_resolve_location(
                        root, location.pdf_path, "pdf_path"
                    ),
                    processed_document_path=_resolve_location(
                        root,
                        location.processed_document_path,
                        "processed_document_path",
                    ),
                )
                for location in locations
            )
            return PdfProcessedDocuments(documents=documents)
        except ProcessedPdfDocumentDeserializationError:
            raise
        except (
            json.JSONDecodeError,
            OSError,
            RecursionError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
        ) as error:
            raise ProcessedPdfDocumentDeserializationError(
                f"cannot deserialize processed-document corpus: {error}"
            ) from error


def _project_pages(
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


def _positive_limit(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _read_regular_file(path: Path, *, limit: int, label: str) -> bytes:
    if not isinstance(path, Path):
        raise TypeError(f"{label} path must be a Path")
    source = path.expanduser().absolute()
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"{label} must be a non-symlinked regular file")
    size = source.stat().st_size
    if size > limit:
        raise ValueError(f"{label} exceeds its byte limit")
    content = source.read_bytes()
    if len(content) != size or len(content) > limit:
        raise ValueError(f"{label} changed while it was read")
    return content


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


def _relative_path(value: object, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    if len(value) > _MAX_IDENTITY_CHARACTERS:
        raise ValueError(f"{field} is too long")
    path = PurePosixPath(value)
    _validate_relative_path(path, field)
    if path.as_posix() != value:
        raise ValueError(f"{field} must be normalized")
    return path


def _resolve_location(root: Path, relative: PurePosixPath, field: str) -> Path:
    unresolved = root.joinpath(*relative.parts)
    resolved = unresolved.resolve(strict=True)
    if not resolved.is_relative_to(root) or resolved != unresolved:
        raise ValueError(f"{field} escapes its root or traverses a symlink")
    return resolved


def _manifest_locations(
    value: object, max_documents: int
) -> tuple[ProcessedPdfDocumentLocation, ...]:
    if not isinstance(value, dict):
        raise ValueError("processed-documents manifest must be an object")
    expected = {"schema_version", "items"}
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise ValueError(
            "processed-documents manifest fields are invalid: "
            f"missing={missing}, extra={extra}"
        )
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != PROCESSED_PDF_DOCUMENTS_SCHEMA_VERSION
    ):
        raise ValueError("unsupported processed-documents schema version")
    items = value["items"]
    if not isinstance(items, list) or not items:
        raise ValueError("processed-documents items must be a non-empty array")
    if len(items) > max_documents:
        raise ValueError("processed-documents manifest exceeds the item limit")
    locations = tuple(
        ProcessedPdfDocumentLocation.from_dict(item) for item in items
    )
    for field, values in (
        (
            "citation_key",
            tuple(location.citation_key for location in locations),
        ),
        (
            "pdf_path",
            tuple(location.pdf_path.as_posix() for location in locations),
        ),
        (
            "processed_document_path",
            tuple(
                location.processed_document_path.as_posix()
                for location in locations
            ),
        ),
    ):
        if len(values) != len(set(values)):
            raise ValueError(
                f"processed-documents manifest contains duplicate {field}"
            )
    return locations


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"invalid JSON number: {value}")


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
            pages=_project_pages(extraction),
            extraction=extraction,
        )


__all__ = [
    "PROCESSED_PDF_DOCUMENTS_SCHEMA_VERSION",
    "PdfDocumentProcessor",
    "PdfProcessedDocument",
    "ProcessedPdfDocumentDeserializationError",
    "ProcessedPdfDocumentDeserializer",
    "ProcessedPdfDocumentLocation",
    "PdfProcessedDocuments",
    "ProcessedPdfDocumentsDeserializer",
    "ProcessedPdfPage",
]

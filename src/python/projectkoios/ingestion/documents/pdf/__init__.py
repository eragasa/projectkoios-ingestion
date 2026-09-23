from __future__ import annotations

from importlib import import_module
from typing import Any
from warnings import warn

_DEPRECATED_EXPORTS = {
    "PROCESSED_PDF_DOCUMENTS_SCHEMA_VERSION": (
        "projectkoios.ingestion.documents.pdf.models",
        "PROCESSED_PDF_DOCUMENTS_SCHEMA_VERSION",
    ),
    "BaseDeserializer": (
        "projectkoios.ingestion.documents.pdf.deserialization",
        "BaseDeserializer",
    ),
    "BaseProcessedDocumentDeserializer": (
        "projectkoios.ingestion.documents.pdf.deserialization",
        "BaseProcessedDocumentDeserializer",
    ),
    "BaseProcessedDocumentsDeserializer": (
        "projectkoios.ingestion.documents.pdf.deserialization",
        "BaseProcessedDocumentsDeserializer",
    ),
    "PdfDocumentProcessor": (
        "projectkoios.ingestion.documents.pdf.processor",
        "PdfDocumentProcessor",
    ),
    "PdfProcessedDocument": (
        "projectkoios.ingestion.documents.pdf.models",
        "PdfProcessedDocument",
    ),
    "PdfProcessedDocuments": (
        "projectkoios.ingestion.documents.pdf.models",
        "PdfProcessedDocuments",
    ),
    "ProcessedPdfDocument": (
        "projectkoios.ingestion.documents.pdf.processed_document",
        "ProcessedPdfDocument",
    ),
    "ProcessedPdfDocumentDeserializationError": (
        "projectkoios.ingestion.documents.pdf.errors",
        "ProcessedPdfDocumentDeserializationError",
    ),
    "ProcessedPdfDocumentDeserializer": (
        "projectkoios.ingestion.documents.pdf.processed_document",
        "ProcessedPdfDocumentDeserializer",
    ),
    "ProcessedPdfDocumentError": (
        "projectkoios.ingestion.documents.pdf.errors",
        "ProcessedPdfDocumentError",
    ),
    "ProcessedPdfDocumentLocation": (
        "projectkoios.ingestion.documents.pdf.models",
        "ProcessedPdfDocumentLocation",
    ),
    "ProcessedPdfDocumentPersistenceError": (
        "projectkoios.ingestion.documents.pdf.errors",
        "ProcessedPdfDocumentPersistenceError",
    ),
    "ProcessedPdfDocumentsDeserializationError": (
        "projectkoios.ingestion.documents.pdf.errors",
        "ProcessedPdfDocumentsDeserializationError",
    ),
    "ProcessedPdfDocumentsDeserializer": (
        "projectkoios.ingestion.documents.pdf.processed_documents",
        "ProcessedPdfDocumentsDeserializer",
    ),
    "ProcessedPdfPage": (
        "projectkoios.ingestion.documents.pdf.models",
        "ProcessedPdfPage",
    ),
}


def __getattr__(name: str) -> Any:
    target = _DEPRECATED_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    warn(
        f"projectkoios.ingestion.documents.pdf.{name} is deprecated; "
        f"import {attribute_name} from {module_name}",
        DeprecationWarning,
        stacklevel=2,
    )
    return getattr(import_module(module_name), attribute_name)


def __dir__() -> list[str]:
    return sorted((*globals(), *_DEPRECATED_EXPORTS))


__all__ = sorted(_DEPRECATED_EXPORTS)

from __future__ import annotations


class ProcessedPdfDocumentError(ValueError):
    """Base error for processed-PDF document operations."""


class ProcessedPdfDocumentDeserializationError(ProcessedPdfDocumentError):
    """Raised when one location cannot produce a verified document."""


class ProcessedPdfDocumentsDeserializationError(
    ProcessedPdfDocumentDeserializationError
):
    """Raised when an explicit corpus manifest cannot be reconstructed."""


class ProcessedPdfDocumentPersistenceError(ProcessedPdfDocumentError):
    """Raised when processed-PDF evidence cannot be persisted safely."""


__all__ = [
    "ProcessedPdfDocumentDeserializationError",
    "ProcessedPdfDocumentError",
    "ProcessedPdfDocumentPersistenceError",
    "ProcessedPdfDocumentsDeserializationError",
]

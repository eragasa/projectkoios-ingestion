from __future__ import annotations

import inspect

import projectkoios.ingestion.documents.pdf as legacy_pdf
import projectkoios.ingestion.documents.pdf.deserialization as deserialization
import pytest
from projectkoios.ingestion.base import BaseProcessedDocument
from projectkoios.ingestion.documents.pdf.deserialization import (
    BaseProcessedDocumentDeserializer,
    BaseProcessedDocumentsDeserializer,
)
from projectkoios.ingestion.documents.pdf.errors import (
    ProcessedPdfDocumentDeserializationError,
)
from projectkoios.ingestion.documents.pdf.models import (
    PdfProcessedDocument,
    PdfProcessedDocuments,
    ProcessedPdfDocumentLocation,
    ProcessedPdfPage,
)
from projectkoios.ingestion.documents.pdf.processed_document import (
    ProcessedPdfDocument,
    ProcessedPdfDocumentDeserializer,
)
from projectkoios.ingestion.documents.pdf.processed_documents import (
    ProcessedPdfDocumentsDeserializer,
)


def test__pdf_document_models__are_collected_in_models_module() -> None:
    model_types = (
        ProcessedPdfPage,
        PdfProcessedDocument,
        PdfProcessedDocuments,
        ProcessedPdfDocumentLocation,
    )

    assert all(
        model_type.__module__ == "projectkoios.ingestion.documents.pdf.models"
        for model_type in model_types
    )


def test__pdf_document_errors__are_collected_in_errors_module() -> None:
    assert ProcessedPdfDocumentDeserializationError.__module__ == (
        "projectkoios.ingestion.documents.pdf.errors"
    )


def test__deserialization_module__defines_only_base_classes() -> None:
    defined_classes = {
        name
        for name, value in inspect.getmembers(deserialization, inspect.isclass)
        if value.__module__ == deserialization.__name__
    }

    assert defined_classes == {
        "BaseDeserializer",
        "BaseProcessedDocumentDeserializer",
        "BaseProcessedDocumentsDeserializer",
    }


def test__ProcessedPdfDocument__encapsulates_concrete_deserializer() -> None:
    deserializer = ProcessedPdfDocumentDeserializer()
    processed_document = ProcessedPdfDocument(deserializer)

    assert processed_document.deserializer is deserializer
    assert isinstance(
        deserializer,
        BaseProcessedDocumentDeserializer,
    )


def test__legacy_pdf_import_surface__emits_deprecation_warning() -> None:
    with pytest.warns(DeprecationWarning, match="is deprecated"):
        legacy_model = legacy_pdf.PdfProcessedDocument

    assert legacy_model is PdfProcessedDocument


def test__plural_deserializer__uses_base_processed_document_contract() -> None:
    assert issubclass(PdfProcessedDocument, BaseProcessedDocument)
    assert issubclass(
        ProcessedPdfDocumentsDeserializer,
        BaseProcessedDocumentsDeserializer,
    )

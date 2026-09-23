from __future__ import annotations

import json
from pathlib import Path

from projectkoios.ingestion.documents.pdf.deserialization import (
    BaseProcessedDocumentsDeserializer,
)
from projectkoios.ingestion.documents.pdf.errors import (
    ProcessedPdfDocumentDeserializationError,
    ProcessedPdfDocumentsDeserializationError,
)
from projectkoios.ingestion.documents.pdf.models import (
    MAX_CORPUS_DOCUMENTS,
    PROCESSED_PDF_DOCUMENTS_SCHEMA_VERSION,
    PdfProcessedDocument,
    PdfProcessedDocuments,
    ProcessedPdfDocumentLocation,
)
from projectkoios.ingestion.documents.pdf.processed_document import (
    ProcessedPdfDocument,
    ProcessedPdfDocumentDeserializer,
)

_MAX_MANIFEST_BYTES = 5_000_000


class ProcessedPdfDocumentsDeserializer(
    BaseProcessedDocumentsDeserializer[
        PdfProcessedDocument,
        PdfProcessedDocuments,
    ]
):
    """Load an ordered corpus from one explicit path manifest."""

    name = "pdf-processed-documents-deserializer"
    version = "1"

    def __init__(
        self,
        document_deserializer: ProcessedPdfDocumentDeserializer | None = None,
        *,
        max_manifest_bytes: int = _MAX_MANIFEST_BYTES,
        max_documents: int = MAX_CORPUS_DOCUMENTS,
    ) -> None:
        self.processed_document = ProcessedPdfDocument(document_deserializer)
        self.max_manifest_bytes = self._positive_limit(
            max_manifest_bytes,
            "max_manifest_bytes",
        )
        self.max_documents = self._positive_limit(
            max_documents,
            "max_documents",
        )
        if self.max_documents > MAX_CORPUS_DOCUMENTS:
            raise ValueError(
                f"max_documents cannot exceed {MAX_CORPUS_DOCUMENTS}"
            )

    def deserialize(self, manifest_path: Path) -> PdfProcessedDocuments:
        try:
            manifest = manifest_path.expanduser().absolute()
            manifest_bytes = self._read_regular_file(
                manifest,
                limit=self.max_manifest_bytes,
                label="processed-documents manifest",
            )
            value = json.loads(
                manifest_bytes.decode("utf-8", errors="strict"),
                object_pairs_hook=self._object_without_duplicates,
                parse_constant=self._reject_json_constant,
            )
            locations = self._manifest_locations(
                value,
                self.max_documents,
            )
            root = manifest.parent.resolve(strict=True)
            documents = tuple(
                self.processed_document.deserialize(
                    citation_key=location.citation_key,
                    bibtex_path=self._resolve_location(
                        root,
                        location.bibtex_path,
                        "bibtex_path",
                    ),
                    pdf_path=self._resolve_location(
                        root,
                        location.pdf_path,
                        "pdf_path",
                    ),
                    processed_document_path=self._resolve_location(
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
            raise ProcessedPdfDocumentsDeserializationError(
                f"cannot deserialize processed-document corpus: {error}"
            ) from error

    @staticmethod
    def _manifest_locations(
        value: object,
        max_documents: int,
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
            raise ValueError(
                "processed-documents items must be a non-empty array"
            )
        if len(items) > max_documents:
            raise ValueError(
                "processed-documents manifest exceeds the item limit"
            )
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


__all__ = ["ProcessedPdfDocumentsDeserializer"]

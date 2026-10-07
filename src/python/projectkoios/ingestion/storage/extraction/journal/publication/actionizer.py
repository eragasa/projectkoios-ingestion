"""Typed disk-only publication of one validated extraction artifact."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.cache import deserialize_extraction_result
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.verifier import SHA256Verifier
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.artifact.validation.reader.base import (  # noqa: E501
    ExtractionArtifactReader,
)
from projectkoios.ingestion.storage.extraction.artifact.validation.reader.error import (  # noqa: E501
    ExtractionArtifactReaderError,
)
from projectkoios.ingestion.storage.extraction.journal.publication.backend.base import (  # noqa: E501
    ValidatedExtractionJournalPublicationBackend,
)
from projectkoios.ingestion.storage.extraction.journal.publication.backend.error import (  # noqa: E501
    ValidatedExtractionJournalPublicationBackendError,
)
from projectkoios.ingestion.storage.extraction.journal.publication.request import (  # noqa: E501
    ValidatedExtractionJournalPublicationRequest,
)
from projectkoios.ingestion.storage.extraction.journal.publication.result import (  # noqa: E501
    ValidatedExtractionJournalPublicationResult,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)


class ValidatedExtractionJournalPublicationActionizer(
    DataObjectActionizer[
        ValidatedExtractionJournalPublicationRequest,
        ValidatedExtractionJournalPublicationResult,
    ]
):
    """Revalidate exact bytes and publish to the authoritative journal."""

    __slots__ = ("reader", "backend")

    actionizer_name = "validated-extraction-journal-publication"
    actionizer_version = "1"

    def __init__(
        self,
        *,
        reader: ExtractionArtifactReader,
        backend: ValidatedExtractionJournalPublicationBackend,
    ) -> None:
        if not isinstance(reader, ExtractionArtifactReader):
            raise TypeError("reader must be an ExtractionArtifactReader")
        if not isinstance(
            backend, ValidatedExtractionJournalPublicationBackend
        ):
            raise TypeError(
                "backend must be a ValidatedExtractionJournalPublicationBackend"
            )
        self.reader = reader
        self.backend = backend

    def action(
        self,
        *,
        request: ValidatedExtractionJournalPublicationRequest,
    ) -> ValidatedExtractionJournalPublicationResult:
        if not isinstance(
            request, ValidatedExtractionJournalPublicationRequest
        ):
            raise TypeError(
                "request must be a ValidatedExtractionJournalPublicationRequest"
            )
        expected = request.validation_request
        try:
            content = self.reader.read(
                artifact_reference=expected.artifact_reference,
                authority_id=expected.authority_id,
                maximum_bytes=expected.MAXIMUM_ARTIFACT_BYTES,
            )
        except ExtractionArtifactReaderError as error:
            return self._failed(request, error.disposition, error.code)
        if (
            type(content) is not bytes
            or len(content) != expected.expected_artifact_byte_size
            or not SHA256Verifier.verify(
                content=content, expected=expected.expected_artifact_sha256
            )
        ):
            return self._failed(
                request,
                ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                "artifact_bytes_differ",
            )
        try:
            extraction = deserialize_extraction_result(
                content.decode("utf-8", errors="strict")
            )
            publication_request = ExtractionPublicationRequest.create(
                extraction=extraction
            )
            payload = CanonicalJsonSerializer.serialize_text(
                extraction
            ).encode()
        except TypeError, UnicodeError, ValueError:
            return self._failed(
                request,
                ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                "invalid_extraction_artifact",
            )
        actual = (
            extraction.document.source.content_hash,
            extraction.document.document_id,
            extraction.manifest.manifest_id,
            SHA256Fingerprinter.fingerprint(content=payload),
            len(payload),
            publication_request.request_id,
            len(extraction.document.pages),
            sum(len(page.blocks) for page in extraction.document.pages),
            len(extraction.warnings),
        )
        planned = (
            expected.expected_source_sha256,
            expected.expected_document_id,
            expected.expected_manifest_id,
            expected.expected_payload_sha256,
            expected.expected_payload_byte_size,
            expected.expected_publication_request_id,
            expected.expected_page_count,
            expected.expected_block_count,
            expected.expected_warning_count,
        )
        if actual != planned:
            return self._failed(
                request,
                ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE,
                "extraction_identity_differs",
            )
        try:
            publication, record = self.backend.publish_validated(
                journal_reference=request.journal_reference,
                authority_id=request.authority_id,
                request=publication_request,
            )
        except ValidatedExtractionJournalPublicationBackendError as error:
            return self._failed(request, error.disposition, error.code)
        if (
            record.request_id != expected.expected_publication_request_id
            or record.document_id != expected.expected_document_id
            or record.manifest_id != expected.expected_manifest_id
            or record.payload_sha256 != expected.expected_payload_sha256
            or record.payload_byte_size != expected.expected_payload_byte_size
            or publication.request_id != record.request_id
            or publication.journal_sequence != record.sequence
        ):
            return self._failed(
                request,
                ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE,
                "journal_publication_evidence_differs",
            )
        return ValidatedExtractionJournalPublicationResult.completed(
            request=request,
            publication=publication,
            record=record,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )

    def _failed(
        self,
        request: ValidatedExtractionJournalPublicationRequest,
        disposition: ExtractionActionDisposition,
        failure_code: str,
    ) -> ValidatedExtractionJournalPublicationResult:
        return ValidatedExtractionJournalPublicationResult.failed(
            request=request,
            disposition=disposition,
            failure_code=failure_code,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )

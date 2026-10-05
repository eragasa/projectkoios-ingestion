"""Typed validation action for one retained ExtractionResult artifact."""

from __future__ import annotations

import hashlib

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.cache import deserialize_extraction_result
from projectkoios.ingestion.serialization import serialize_contract
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.artifact_validation.reader import (  # noqa: E501
    ExtractionArtifactReader,
)
from projectkoios.ingestion.storage.extraction.artifact_validation.reader_error import (  # noqa: E501
    ExtractionArtifactReaderError,
)
from projectkoios.ingestion.storage.extraction.artifact_validation.request import (  # noqa: E501
    ExistingExtractionArtifactValidationRequest,
)
from projectkoios.ingestion.storage.extraction.artifact_validation.result import (  # noqa: E501
    ExistingExtractionArtifactValidationResult,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)


class ExistingExtractionArtifactValidationActionizer(
    DataObjectActionizer[
        ExistingExtractionArtifactValidationRequest,
        ExistingExtractionArtifactValidationResult,
    ]
):
    """Validate exact artifact bytes without retaining their subject graph."""

    __slots__ = ("reader",)

    actionizer_name = "existing-extraction-artifact-validation"
    actionizer_version = "1"

    def __init__(self, *, reader: ExtractionArtifactReader) -> None:
        if not isinstance(reader, ExtractionArtifactReader):
            raise TypeError("reader must be an ExtractionArtifactReader")
        self.reader = reader

    def action(
        self,
        *,
        request: ExistingExtractionArtifactValidationRequest,
    ) -> ExistingExtractionArtifactValidationResult:
        if not isinstance(request, ExistingExtractionArtifactValidationRequest):
            raise TypeError(
                "request must be an ExistingExtractionArtifactValidationRequest"
            )
        try:
            content = self.reader.read(
                artifact_reference=request.artifact_reference,
                authority_id=request.authority_id,
                maximum_bytes=request.MAXIMUM_ARTIFACT_BYTES,
            )
        except ExtractionArtifactReaderError as error:
            return self._failed(
                request=request,
                disposition=error.disposition,
                failure_code=error.code,
            )
        if (
            type(content) is not bytes
            or len(content) != request.expected_artifact_byte_size
            or hashlib.sha256(content).hexdigest()
            != request.expected_artifact_sha256
        ):
            return self._failed(
                request=request,
                disposition=ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                failure_code="artifact_bytes_differ",
            )
        try:
            extraction = deserialize_extraction_result(
                content.decode("utf-8", errors="strict")
            )
            publication_request = ExtractionPublicationRequest.create(
                extraction=extraction
            )
            payload = serialize_contract(extraction).encode("utf-8")
        except TypeError, UnicodeError, ValueError:
            return self._failed(
                request=request,
                disposition=ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                failure_code="invalid_extraction_artifact",
            )
        actual = (
            extraction.document.source.content_hash,
            extraction.document.document_id,
            extraction.manifest.manifest_id,
            hashlib.sha256(payload).hexdigest(),
            len(payload),
            publication_request.request_id,
            len(extraction.document.pages),
            sum(len(page.blocks) for page in extraction.document.pages),
            len(extraction.warnings),
        )
        expected = (
            request.expected_source_sha256,
            request.expected_document_id,
            request.expected_manifest_id,
            request.expected_payload_sha256,
            request.expected_payload_byte_size,
            request.expected_publication_request_id,
            request.expected_page_count,
            request.expected_block_count,
            request.expected_warning_count,
        )
        if actual != expected:
            return self._failed(
                request=request,
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                failure_code="extraction_identity_differs",
            )
        return ExistingExtractionArtifactValidationResult.completed(
            request=request,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )

    def _failed(
        self,
        *,
        request: ExistingExtractionArtifactValidationRequest,
        disposition: ExtractionActionDisposition,
        failure_code: str,
    ) -> ExistingExtractionArtifactValidationResult:
        return ExistingExtractionArtifactValidationResult.failed(
            request=request,
            disposition=disposition,
            failure_code=failure_code,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )

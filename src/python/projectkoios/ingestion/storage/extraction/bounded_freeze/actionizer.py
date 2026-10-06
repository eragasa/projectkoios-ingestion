"""Typed bounded native extraction and create-once freeze action."""

from __future__ import annotations

from io import BytesIO

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.cache import deserialize_extraction_result
from projectkoios.ingestion.models import ExtractionResult, SourceDocument
from projectkoios.ingestion.pdf.adapters.errors import (
    PdfDependencyUnavailableError,
)
from projectkoios.ingestion.serialization import serialize_contract
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.verifier import SHA256Verifier
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.artifact_validation.request import (  # noqa: E501
    ExistingExtractionArtifactValidationRequest,
)
from projectkoios.ingestion.storage.extraction.artifact_validation.result import (  # noqa: E501
    ExistingExtractionArtifactValidationResult,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.error import (
    BoundedExtractionFreezeError,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.extraction_error import (  # noqa: E501
    FreezableSourceExtractionError,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.extractor import (
    FreezableSourceExtractor,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.request import (
    BoundedExtractionFreezeRequest,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.result import (
    BoundedExtractionFreezeResult,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.source_reader import (  # noqa: E501
    ExtractionSourceReader,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.store import (
    ExtractionFreezeStore,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)


class BoundedExtractionFreezeActionizer(
    DataObjectActionizer[
        BoundedExtractionFreezeRequest,
        BoundedExtractionFreezeResult,
    ]
):
    """Reuse a valid frozen result or extract and create it exactly once."""

    __slots__ = ("source_reader", "artifact_store", "extractor")

    actionizer_name = "bounded-extraction-freeze"
    actionizer_version = "1"

    def __init__(
        self,
        *,
        source_reader: ExtractionSourceReader,
        artifact_store: ExtractionFreezeStore,
        extractor: FreezableSourceExtractor,
    ) -> None:
        if not isinstance(source_reader, ExtractionSourceReader):
            raise TypeError("source_reader must be an ExtractionSourceReader")
        if not isinstance(artifact_store, ExtractionFreezeStore):
            raise TypeError("artifact_store must be an ExtractionFreezeStore")
        if not isinstance(extractor, FreezableSourceExtractor):
            raise TypeError("extractor must be a FreezableSourceExtractor")
        self.source_reader = source_reader
        self.artifact_store = artifact_store
        self.extractor = extractor

    def action(
        self,
        *,
        request: BoundedExtractionFreezeRequest,
    ) -> BoundedExtractionFreezeResult:
        if not isinstance(request, BoundedExtractionFreezeRequest):
            raise TypeError("request must be a BoundedExtractionFreezeRequest")
        try:
            existing = self.artifact_store.read_if_exists(
                artifact_reference=request.artifact_reference,
                authority_id=request.artifact_read_authority_id,
                maximum_bytes=request.MAXIMUM_ARTIFACT_BYTES,
            )
        except BoundedExtractionFreezeError as error:
            return self._failed(request, error.disposition, error.code)
        if existing is not None:
            return self._complete_from_bytes(request, existing, created=False)
        try:
            material = self.source_reader.read_source(
                source_reference=request.source_reference,
                authority_id=request.source_authority_id,
                maximum_bytes=request.MAXIMUM_SOURCE_BYTES,
            )
        except BoundedExtractionFreezeError as error:
            return self._failed(request, error.disposition, error.code)
        if (
            len(material.content) != request.expected_source_byte_size
            or not SHA256Verifier.verify(
                content=material.content,
                expected=request.expected_source_sha256,
            )
            or not SHA256Verifier.verify(
                content=material.locator.encode(),
                expected=request.expected_locator_sha256,
            )
        ):
            return self._failed(
                request,
                ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                "source_evidence_differs",
            )
        source = SourceDocument.from_bytes(
            material.content,
            source_id=request.source_id,
            media_type=request.media_type,
            locator=material.locator,
        )
        try:
            extractor_version = self.extractor.extraction_version
            cache_key = self.extractor.cache_key(source)
        except PdfDependencyUnavailableError:
            return self._failed(
                request,
                ExtractionActionDisposition.AUTHORITY_REQUIRED,
                "extractor_resource_unavailable",
            )
        if (
            self.extractor.name != request.extractor_name
            or extractor_version != request.expected_extractor_version
            or self.extractor.configuration_digest
            != request.configuration_digest
            or cache_key != request.expected_cache_key
        ):
            return self._failed(
                request,
                ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE,
                "extractor_identity_differs",
            )
        try:
            extraction = self.extractor.extract_for_freeze(
                source,
                BytesIO(material.content),
            )
        except PdfDependencyUnavailableError:
            return self._failed(
                request,
                ExtractionActionDisposition.AUTHORITY_REQUIRED,
                "extractor_resource_unavailable",
            )
        except FreezableSourceExtractionError:
            return self._failed(
                request,
                ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                "source_extraction_failed",
            )
        if not self._matches_request(request, extraction):
            return self._failed(
                request,
                ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE,
                "extraction_identity_differs",
            )
        content = serialize_contract(extraction).encode()
        if not content or len(content) > request.MAXIMUM_ARTIFACT_BYTES:
            return self._failed(
                request,
                ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                "extraction_artifact_size_invalid",
            )
        try:
            created = self.artifact_store.create_once(
                artifact_reference=request.artifact_reference,
                authority_id=request.artifact_write_authority_id,
                content=content,
                maximum_bytes=request.MAXIMUM_ARTIFACT_BYTES,
            )
        except BoundedExtractionFreezeError as error:
            return self._failed(request, error.disposition, error.code)
        return self._completed(request, extraction, content, created=created)

    def _complete_from_bytes(
        self,
        request: BoundedExtractionFreezeRequest,
        content: bytes,
        *,
        created: bool,
    ) -> BoundedExtractionFreezeResult:
        if not content or len(content) > request.MAXIMUM_ARTIFACT_BYTES:
            return self._failed(
                request,
                ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                "frozen_extraction_artifact_size_invalid",
            )
        try:
            extraction = deserialize_extraction_result(
                content.decode("utf-8", errors="strict")
            )
        except TypeError, UnicodeError, ValueError:
            return self._failed(
                request,
                ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                "frozen_extraction_artifact_invalid",
            )
        if serialize_contract(extraction).encode() != content:
            return self._failed(
                request,
                ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
                "frozen_extraction_artifact_not_canonical",
            )
        if not self._matches_request(request, extraction):
            return self._failed(
                request,
                ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE,
                "frozen_extraction_identity_differs",
            )
        return self._completed(request, extraction, content, created=created)

    def _completed(
        self,
        request: BoundedExtractionFreezeRequest,
        extraction: ExtractionResult,
        content: bytes,
        *,
        created: bool,
    ) -> BoundedExtractionFreezeResult:
        publication = ExtractionPublicationRequest.create(extraction=extraction)
        validation_request = ExistingExtractionArtifactValidationRequest.create(
            artifact_reference=request.artifact_reference,
            authority_id=request.artifact_read_authority_id,
            expected_artifact_sha256=SHA256Fingerprinter.fingerprint(
                content=content
            ),
            expected_artifact_byte_size=len(content),
            expected_source_sha256=request.expected_source_sha256,
            expected_document_id=extraction.document.document_id,
            expected_manifest_id=extraction.manifest.manifest_id,
            expected_payload_sha256=SHA256Fingerprinter.fingerprint(
                content=content
            ),
            expected_payload_byte_size=len(content),
            expected_publication_request_id=publication.request_id,
            expected_page_count=len(extraction.document.pages),
            expected_block_count=sum(
                len(page.blocks) for page in extraction.document.pages
            ),
            expected_warning_count=len(extraction.warnings),
        )
        validation_result = (
            ExistingExtractionArtifactValidationResult.completed(
                request=validation_request,
                actionizer_name=self.actionizer_name,
                actionizer_version=self.actionizer_version,
            )
        )
        return BoundedExtractionFreezeResult.completed(
            request=request,
            created=created,
            validation_request=validation_request,
            validation_result=validation_result,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )

    @staticmethod
    def _matches_request(
        request: BoundedExtractionFreezeRequest,
        extraction: ExtractionResult,
    ) -> bool:
        source = extraction.document.source
        manifest = extraction.manifest
        return (
            source.source_id == request.source_id
            and source.content_hash == request.expected_source_sha256
            and source.byte_length == request.expected_source_byte_size
            and SHA256Verifier.verify(
                content=source.locator.encode(),
                expected=request.expected_locator_sha256,
            )
            and source.media_type == request.media_type
            and len(extraction.document.pages) == request.expected_page_count
            and manifest.extractor_name == request.extractor_name
            and manifest.extractor_version == request.expected_extractor_version
            and manifest.configuration_digest == request.configuration_digest
            and manifest.cache_key == request.expected_cache_key
        )

    def _failed(
        self,
        request: BoundedExtractionFreezeRequest,
        disposition: ExtractionActionDisposition,
        failure_code: str,
    ) -> BoundedExtractionFreezeResult:
        return BoundedExtractionFreezeResult.failed(
            request=request,
            disposition=disposition,
            failure_code=failure_code,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )

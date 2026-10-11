"""Durable one-document page-projection publication action."""

from __future__ import annotations

from typing import Never

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.artifact.managed.verification.actionizer import (
    ManagedArtifactVerificationActionizer,
)
from projectkoios.ingestion.artifact.managed.verification.error import (
    ManagedArtifactVerificationError,
)
from projectkoios.ingestion.artifact.managed.verification.provider import (
    ManagedArtifactByteProvider,
)
from projectkoios.ingestion.artifact.managed.verification.request import (
    ManagedArtifactVerificationRequest,
)
from projectkoios.ingestion.json.error import JsonError
from projectkoios.ingestion.json.limits.error import JsonLimitError
from projectkoios.ingestion.page.projection.enrichment.result import (
    PageProjectionEvidenceEnrichmentResult,
)
from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.publication.code import (
    PageProjectionPublicationCodeInventory,
)
from projectkoios.ingestion.page.projection.publication.configuration import (
    PageProjectionPublicationConfiguration,
)
from projectkoios.ingestion.page.projection.publication.error import (
    PageProjectionPublicationError,
    PageProjectionPublicationFailureReason,
)
from projectkoios.ingestion.page.projection.publication.evidence import (
    PageProjectionPublicationEvidence,
)
from projectkoios.ingestion.page.projection.publication.production import (
    derive_native_pdf_publication_evidence,
)
from projectkoios.ingestion.page.projection.publication.receipt import (
    PageProjectionPublicationReceipt,
)
from projectkoios.ingestion.page.projection.publication.request import (
    PageProjectionPublicationRequest,
)
from projectkoios.ingestion.page.projection.publication.result import (
    PageProjectionPublicationResult,
)
from projectkoios.ingestion.page.projection.publication.status import (
    PageProjectionPublicationProfile,
)
from projectkoios.ingestion.page.projection.publication.store import (
    PageProjectionPublicationStore,
)
from projectkoios.ingestion.pdf.adapters.errors import (
    PdfDependencyUnavailableError,
)
from projectkoios.ingestion.pdf.adapters.pymupdf.extraction import (
    PyMuPdfExtractor,
)
from projectkoios.ingestion.pdf.extraction.contracts import PdfPageLimitError
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


class PageProjectionPublicationActionizer(
    DataObjectActionizer[
        PageProjectionPublicationRequest,
        PageProjectionPublicationResult,
    ]
):
    """Verify, derive, and durably publish one exact PDF owner lifecycle."""

    __slots__ = (
        "configuration",
        "pipeline_configuration_id",
        "provider",
        "store",
    )

    def __init__(
        self,
        *,
        provider: ManagedArtifactByteProvider,
        store: PageProjectionPublicationStore,
        configuration: PageProjectionPublicationConfiguration,
    ) -> None:
        if not isinstance(provider, ManagedArtifactByteProvider):
            raise TypeError("provider must be a ManagedArtifactByteProvider")
        if not isinstance(store, PageProjectionPublicationStore):
            raise TypeError("store must be a PageProjectionPublicationStore")
        if type(configuration) is not PageProjectionPublicationConfiguration:
            raise TypeError("configuration has an unsupported type")
        self.provider = provider
        self.store = store
        self.configuration = configuration
        try:
            extractor = PyMuPdfExtractor(
                low_text_character_threshold=(
                    configuration.low_text_character_threshold
                ),
                maximum_pages=configuration.maximum_page_count,
            )
            pipeline_id = derive_page_projection_publication_pipeline_id(
                provider_implementation_id=provider.implementation_id,
                configuration=configuration,
                extractor=extractor,
            )
        except PdfDependencyUnavailableError as error:
            raise PageProjectionPublicationError(
                reason=(
                    PageProjectionPublicationFailureReason.DEPENDENCY_UNAVAILABLE
                ),
                message="configured PDF dependency is unavailable",
            ) from error
        self.pipeline_configuration_id = pipeline_id

    def action(
        self, *, request: PageProjectionPublicationRequest
    ) -> PageProjectionPublicationResult:
        """Return a post-commit reread result or one closed typed failure."""
        if type(request) is not PageProjectionPublicationRequest:
            raise PageProjectionPublicationError(
                reason=PageProjectionPublicationFailureReason.INVALID_REQUEST,
                message="request has an unsupported type",
            )
        try:
            with self.store.open_journal(
                source_artifact_id=request.source_artifact.artifact_id
            ) as journal:
                replay = journal.replay(request=request)
                if replay is not None:
                    return replay
                if (
                    request.source_artifact.media_type
                    is not ManagedArtifactMediaType.APPLICATION_PDF
                ):
                    raise PageProjectionPublicationError(
                        reason=(
                            PageProjectionPublicationFailureReason.UNSUPPORTED_MEDIA
                        ),
                        message="publication source media is unsupported",
                    )
                if (
                    self.configuration.profile
                    is not PageProjectionPublicationProfile.NATIVE_PDF_TEXT_V1
                ):
                    raise PageProjectionPublicationError(
                        reason=(
                            PageProjectionPublicationFailureReason.UNSUPPORTED_PROFILE
                        ),
                        message="publication pipeline profile is unsupported",
                    )
                if (
                    request.expected_pipeline_configuration_id
                    != self.pipeline_configuration_id
                ):
                    raise PageProjectionPublicationError(
                        reason=(
                            PageProjectionPublicationFailureReason.DEPENDENCY_VERSION_DIFFERS
                        ),
                        message="publication pipeline freshness differs",
                    )
                if (
                    request.source_artifact.byte_length
                    > self.configuration.maximum_source_bytes
                    or request.maximum_page_count
                    > self.configuration.maximum_page_count
                    or request.maximum_block_count
                    > self.configuration.maximum_block_count
                ):
                    raise PageProjectionPublicationError(
                        reason=(
                            PageProjectionPublicationFailureReason.RESOURCE_LIMIT_EXCEEDED
                        ),
                        message="request exceeds trusted publication ceilings",
                    )
                journal.require_current(request=request)
                verification = ManagedArtifactVerificationActionizer(
                    provider=self.provider
                ).action(
                    request=ManagedArtifactVerificationRequest(
                        references=ManagedArtifactReferenceInventory(
                            request.source_artifact
                        ),
                        provider_implementation_id=(
                            self.provider.implementation_id
                        ),
                        authority_id=self.configuration.authority_id,
                        maximum_artifact_bytes=(
                            request.source_artifact.byte_length
                        ),
                        maximum_aggregate_bytes=(
                            request.source_artifact.byte_length
                        ),
                        stream_chunk_bytes=(
                            self.configuration.stream_chunk_bytes
                        ),
                    )
                )
                content = read_page_projection_publication_source(
                    provider=self.provider,
                    request=request,
                    configuration=self.configuration,
                )
                evidence = derive_native_pdf_publication_evidence(
                    content=content,
                    source_artifact=request.source_artifact,
                    artifact_verification=verification,
                    configuration=self.configuration,
                    pipeline_configuration_id=(self.pipeline_configuration_id),
                    maximum_page_count=request.maximum_page_count,
                    maximum_block_count=request.maximum_block_count,
                )
                payload = evidence.payload_bytes()
                if len(payload) > self.configuration.maximum_payload_bytes:
                    raise PageProjectionPublicationError(
                        reason=(
                            PageProjectionPublicationFailureReason.RESOURCE_LIMIT_EXCEEDED
                        ),
                        message="publication payload exceeds its trusted bound",
                    )
                receipt = derive_page_projection_publication_receipt(
                    request=request,
                    pipeline_configuration_id=(self.pipeline_configuration_id),
                    evidence=evidence,
                    payload=payload,
                )
                return journal.commit(
                    request=request,
                    receipt=receipt,
                    payload=payload,
                )
        except PageProjectionPublicationError:
            raise
        except Exception as error:
            raise_page_projection_publication_failure(error)


def derive_page_projection_publication_pipeline_id(
    *,
    provider_implementation_id: str,
    configuration: PageProjectionPublicationConfiguration,
    extractor: PyMuPdfExtractor,
) -> str:
    """Derive the exact owner pipeline freshness identity."""
    if type(extractor) is not PyMuPdfExtractor:
        raise TypeError("extractor must be a PyMuPdfExtractor")
    return fingerprint_page_projection_identity(
        namespace="page-projection-publication-pipeline",
        material={
            "artifact_provider_implementation_id": provider_implementation_id,
            "authority_id": configuration.authority_id,
            "contract_version": "1.0",
            "enrichment_contract_version": (
                PageProjectionEvidenceEnrichmentResult.CONTRACT_VERSION
            ),
            "enrichment_processor_id": (
                PageProjectionEvidenceEnrichmentResult.PROCESSOR_ID
            ),
            "enrichment_processor_version": (
                PageProjectionEvidenceEnrichmentResult.PROCESSOR_VERSION
            ),
            "extractor_configuration_digest": (extractor.configuration_digest),
            "extractor_name": extractor.name,
            "extractor_version": extractor.extraction_version,
            "include_figure_captions": False,
            "maximum_block_count": configuration.maximum_block_count,
            "maximum_page_count": configuration.maximum_page_count,
            "maximum_payload_bytes": configuration.maximum_payload_bytes,
            "maximum_projection_inventory_identities": (
                READING_EVIDENCE_LIMITS.maximum_records
            ),
            "maximum_source_bytes": configuration.maximum_source_bytes,
            "profile": configuration.profile,
            "reading_producer_version": "1.0",
            "source_provider_implementation_id": (
                "page-projection-publication-current-source-provider:1.0"
            ),
        },
    )


def read_page_projection_publication_source(
    *,
    provider: ManagedArtifactByteProvider,
    request: PageProjectionPublicationRequest,
    configuration: PageProjectionPublicationConfiguration,
) -> bytes:
    """Reread exact verified bytes under the same bound for extraction."""
    chunks: list[bytes] = []
    byte_length = 0
    with provider.open_chunks(
        reference=request.source_artifact,
        authority_id=configuration.authority_id,
        maximum_bytes=request.source_artifact.byte_length,
        chunk_bytes=configuration.stream_chunk_bytes,
    ) as stream:
        for chunk in stream:
            if type(chunk) is not bytes or not chunk:
                raise ManagedArtifactVerificationError(
                    code="provider_chunk_invalid",
                    message=(
                        "managed artifact provider yielded an invalid chunk"
                    ),
                )
            byte_length += len(chunk)
            if byte_length > request.source_artifact.byte_length:
                raise ManagedArtifactVerificationError(
                    code="artifact_byte_limit_exceeded",
                    message="managed artifact exceeded its exact byte bound",
                )
            chunks.append(chunk)
    content = b"".join(chunks)
    digest = SHA256Fingerprinter.fingerprint(content=content)
    if (
        len(content) != request.source_artifact.byte_length
        or digest != request.source_artifact.sha256
    ):
        raise ManagedArtifactVerificationError(
            code="artifact_bytes_differ",
            message="source bytes changed after managed verification",
        )
    return content


def derive_page_projection_publication_receipt(
    *,
    request: PageProjectionPublicationRequest,
    pipeline_configuration_id: str,
    evidence: PageProjectionPublicationEvidence,
    payload: bytes,
) -> PageProjectionPublicationReceipt:
    """Derive a transport-safe receipt from exact private evidence."""
    enrichment = evidence.enrichment
    projection = enrichment.request.projection
    source_result = projection.request.source_result
    document = source_result.document
    verification = projection.request.artifact_verification_result
    payload_digest = SHA256Fingerprinter.fingerprint(content=payload)
    payload_id = fingerprint_page_projection_identity(
        namespace="page-projection-publication-payload",
        material={
            "contract_version": evidence.CONTRACT_VERSION,
            "payload_sha256": payload_digest,
        },
    )
    return PageProjectionPublicationReceipt(
        pipeline_configuration_id=pipeline_configuration_id,
        source_artifact_id=request.source_artifact.artifact_id,
        source_sha256=request.source_artifact.sha256,
        source_byte_length=request.source_artifact.byte_length,
        source_media_type=request.source_artifact.media_type.value,
        artifact_verification_result_id=verification.result_id,
        extraction_manifest_id=evidence.extraction_manifest_id,
        extracted_document_id=evidence.extracted_document_id,
        reading_source_id=document.source_id.value,
        reading_document_id=document.document_id.value,
        reading_projection_result_id=source_result.projection_result_id.value,
        reading_inventory_id=source_result.inventory.inventory_id.value,
        reading_source_result_id=source_result.result_id,
        page_projection_result_id=projection.result_id,
        page_projection_inventory_id=projection.pages.inventory_id,
        enrichment_result_id=enrichment.result_id,
        enrichment_inventory_id=enrichment.entries.inventory_id,
        page_count=len(projection.pages),
        block_count=projection.pages.block_count,
        enrichment_available_count=enrichment.entries.available_count,
        enrichment_unavailable_count=enrichment.entries.unavailable_count,
        extraction_warning_count=evidence.extraction_warning_count,
        extraction_warning_codes=evidence.extraction_warning_codes,
        reading_limitation_count=len(document.limitations),
        reading_limitation_codes=PageProjectionPublicationCodeInventory(
            *sorted({value.code.value for value in document.limitations})
        ),
        page_projection_limitation_count=len(projection.limitations),
        page_projection_limitation_codes=(
            PageProjectionPublicationCodeInventory(
                *sorted({value.value for value in projection.limitations})
            )
        ),
        payload_id=payload_id,
        payload_sha256=payload_digest,
        payload_byte_length=len(payload),
    )


def raise_page_projection_publication_failure(error: Exception) -> Never:
    """Map all expected lower-level failures to the closed owner seam."""
    if isinstance(error, ManagedArtifactVerificationError):
        code = error.code
        if code in {"artifact_binding_missing", "authority_differs"}:
            reason = (  # noqa: E501
                PageProjectionPublicationFailureReason.SOURCE_BINDING_UNAVAILABLE
            )
        elif code in {
            "artifact_bytes_differ",
            "artifact_byte_limit_exceeded",
            "media_type_differs",
            "media_signature_unsupported",
        }:
            reason = PageProjectionPublicationFailureReason.SOURCE_BYTES_DIFFER
        else:
            reason = PageProjectionPublicationFailureReason.SOURCE_UNAVAILABLE
    elif isinstance(error, PdfDependencyUnavailableError):
        reason = PageProjectionPublicationFailureReason.DEPENDENCY_UNAVAILABLE
    elif isinstance(
        error,
        (
            PdfPageLimitError,
            ReadingEvidenceLimitError,
            JsonLimitError,
            MemoryError,
        ),
    ):
        reason = PageProjectionPublicationFailureReason.RESOURCE_LIMIT_EXCEEDED
    elif isinstance(error, (PageProjectionError, ReadingEvidenceError)):
        reason = (
            PageProjectionPublicationFailureReason.PROJECTION_VALIDATION_FAILED
        )
    elif isinstance(error, JsonError):
        reason = (
            PageProjectionPublicationFailureReason.PUBLICATION_INTEGRITY_INVALID
        )
    elif isinstance(error, OSError):
        reason = (
            PageProjectionPublicationFailureReason.PUBLICATION_STORE_UNAVAILABLE
        )
    elif isinstance(error, (TypeError, ValueError)):
        reason = (
            PageProjectionPublicationFailureReason.PROJECTION_VALIDATION_FAILED
        )
    else:
        reason = PageProjectionPublicationFailureReason.UNEXPECTED
    raise PageProjectionPublicationError(
        reason=reason,
        message="page-projection publication failed without private detail",
    ) from error

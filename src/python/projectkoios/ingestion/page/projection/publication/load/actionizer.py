"""Read-only exact typed publication loading action."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.json.error import JsonError
from projectkoios.ingestion.page.projection.publication.codec import (
    PageProjectionPublicationReceiptCodec,
)
from projectkoios.ingestion.page.projection.publication.load.codec import (
    PageProjectionPublicationPayloadCodec,
)
from projectkoios.ingestion.page.projection.publication.load.error import (
    PageProjectionPublicationLoadError,
    PageProjectionPublicationLoadFailureReason,
)
from projectkoios.ingestion.page.projection.publication.load.request import (
    PageProjectionPublicationLoadRequest,
)
from projectkoios.ingestion.page.projection.publication.load.result import (
    PageProjectionPublicationLoadResult,
)
from projectkoios.ingestion.page.projection.publication.load.source import (
    PageProjectionPublicationPayloadSource,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


class PageProjectionPublicationLoadActionizer(
    DataObjectActionizer[
        PageProjectionPublicationLoadRequest,
        PageProjectionPublicationLoadResult,
    ]
):
    """Verify immutable objects and reconstruct exact defining owner types."""

    __slots__ = ("payload_codec", "receipt_codec", "source")

    def __init__(
        self,
        *,
        source: PageProjectionPublicationPayloadSource,
    ) -> None:
        if not isinstance(source, PageProjectionPublicationPayloadSource):
            raise TypeError(
                "source must be PageProjectionPublicationPayloadSource"
            )
        self.source = source
        self.receipt_codec = PageProjectionPublicationReceiptCodec()
        self.payload_codec = PageProjectionPublicationPayloadCodec()

    def action(
        self,
        *,
        request: PageProjectionPublicationLoadRequest,
    ) -> PageProjectionPublicationLoadResult:
        """Load one exact immutable publication without extraction or writes."""
        if type(request) is not PageProjectionPublicationLoadRequest:
            raise PageProjectionPublicationLoadError(
                reason=PageProjectionPublicationLoadFailureReason.INVALID_REQUEST,
                message="typed-load request has an unsupported type",
            )
        objects = self.source.load(request=request)
        if (
            len(objects.receipt) != request.expected_receipt_byte_length
            or SHA256Fingerprinter.fingerprint(content=objects.receipt)
            != request.expected_receipt_sha256
        ):
            raise PageProjectionPublicationLoadError(
                reason=(
                    PageProjectionPublicationLoadFailureReason.RECEIPT_INTEGRITY_INVALID
                ),
                message="immutable receipt differs from its request",
            )
        try:
            receipt_body = objects.receipt.decode("utf-8", errors="strict")
            receipt = self.receipt_codec.decode(body_json=receipt_body)
        except (JsonError, UnicodeError, TypeError, ValueError) as error:
            raise PageProjectionPublicationLoadError(
                reason=(
                    PageProjectionPublicationLoadFailureReason.RECEIPT_INTEGRITY_INVALID
                ),
                message="immutable receipt schema or identity differs",
            ) from error
        receipt_checks = (
            (receipt.source_artifact_id, request.source_artifact.artifact_id),
            (receipt.source_sha256, request.source_artifact.sha256),
            (receipt.source_byte_length, request.source_artifact.byte_length),
            (
                receipt.source_media_type,
                request.source_artifact.media_type.value,
            ),
            (
                receipt.pipeline_configuration_id,
                request.expected_pipeline_configuration_id,
            ),
            (receipt.publication_id, request.expected_publication_id),
            (receipt.payload_id, request.expected_payload_id),
            (receipt.payload_sha256, request.expected_payload_sha256),
            (receipt.payload_byte_length, request.expected_payload_byte_length),
            (
                receipt.page_projection_result_id,
                request.expected_page_projection_result_id,
            ),
            (
                receipt.enrichment_result_id,
                request.expected_enrichment_result_id,
            ),
        )
        if any(actual != expected for actual, expected in receipt_checks):
            raise PageProjectionPublicationLoadError(
                reason=(
                    PageProjectionPublicationLoadFailureReason.RECEIPT_INTEGRITY_INVALID
                ),
                message="immutable receipt differs from expected identities",
            )
        if (
            len(objects.payload) != receipt.payload_byte_length
            or len(objects.payload) > request.maximum_payload_bytes
            or SHA256Fingerprinter.fingerprint(content=objects.payload)
            != receipt.payload_sha256
        ):
            raise PageProjectionPublicationLoadError(
                reason=(
                    PageProjectionPublicationLoadFailureReason.PAYLOAD_INTEGRITY_INVALID
                ),
                message="immutable payload differs from its receipt",
            )
        try:
            evidence = self.payload_codec.decode(payload=objects.payload)
            projection = evidence.enrichment.request.projection
            result = PageProjectionPublicationLoadResult(
                request=request,
                receipt=receipt,
                projection=projection,
                enrichment=evidence.enrichment,
            )
        except (JsonError, TypeError, ValueError) as error:
            raise PageProjectionPublicationLoadError(
                reason=(
                    PageProjectionPublicationLoadFailureReason.PROJECTION_VALIDATION_FAILED
                ),
                message="typed publication reconstruction failed closed",
            ) from error
        result_checks = (
            (evidence.payload_id(), receipt.payload_id),
            (evidence.extraction_manifest_id, receipt.extraction_manifest_id),
            (evidence.extracted_document_id, receipt.extracted_document_id),
            (projection.result_id, receipt.page_projection_result_id),
            (
                projection.pages.inventory_id,
                receipt.page_projection_inventory_id,
            ),
            (evidence.enrichment.result_id, receipt.enrichment_result_id),
            (
                evidence.enrichment.entries.inventory_id,
                receipt.enrichment_inventory_id,
            ),
            (len(projection.pages), receipt.page_count),
            (projection.pages.block_count, receipt.block_count),
            (
                evidence.enrichment.entries.available_count,
                receipt.enrichment_available_count,
            ),
            (
                evidence.enrichment.entries.unavailable_count,
                receipt.enrichment_unavailable_count,
            ),
        )
        if any(actual != expected for actual, expected in result_checks):
            raise PageProjectionPublicationLoadError(
                reason=(
                    PageProjectionPublicationLoadFailureReason.PAYLOAD_INTEGRITY_INVALID
                ),
                message="typed publication evidence differs from its receipt",
            )
        return result

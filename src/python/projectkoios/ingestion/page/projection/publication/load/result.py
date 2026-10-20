"""Exact typed result of immutable publication loading."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.page.projection.enrichment.result import (
    PageProjectionEvidenceEnrichmentResult,
)
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.publication.load.request import (
    PageProjectionPublicationLoadRequest,
)
from projectkoios.ingestion.page.projection.publication.receipt import (
    PageProjectionPublicationReceipt,
)
from projectkoios.ingestion.page.projection.result import PageProjectionResult


@dataclass(frozen=True, slots=True)
class PageProjectionPublicationLoadResult(DataObjectActionResult):
    """Return the exact defining owner types from one immutable publication."""

    CONTRACT_NAME: ClassVar[str] = "page-projection-publication-load-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request: PageProjectionPublicationLoadRequest
    receipt: PageProjectionPublicationReceipt
    projection: PageProjectionResult
    enrichment: PageProjectionEvidenceEnrichmentResult
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not PageProjectionPublicationLoadRequest:
            raise TypeError(
                "request must be PageProjectionPublicationLoadRequest"
            )
        if type(self.receipt) is not PageProjectionPublicationReceipt:
            raise TypeError("receipt must be PageProjectionPublicationReceipt")
        if type(self.projection) is not PageProjectionResult:
            raise TypeError("projection must be PageProjectionResult")
        if type(self.enrichment) is not PageProjectionEvidenceEnrichmentResult:
            raise TypeError(
                "enrichment must be PageProjectionEvidenceEnrichmentResult"
            )
        if self.enrichment.request.projection != self.projection:
            raise ValueError("enrichment does not bind the exact projection")
        checks = (
            (
                self.receipt.source_artifact_id,
                self.request.source_artifact.artifact_id,
            ),
            (
                self.receipt.pipeline_configuration_id,
                self.request.expected_pipeline_configuration_id,
            ),
            (self.receipt.publication_id, self.request.expected_publication_id),
            (self.receipt.payload_id, self.request.expected_payload_id),
            (self.receipt.payload_sha256, self.request.expected_payload_sha256),
            (
                self.receipt.payload_byte_length,
                self.request.expected_payload_byte_length,
            ),
            (
                self.projection.result_id,
                self.request.expected_page_projection_result_id,
            ),
            (
                self.enrichment.result_id,
                self.request.expected_enrichment_result_id,
            ),
        )
        if any(actual != expected for actual, expected in checks):
            raise ValueError("loaded publication differs from its request")
        object.__setattr__(
            self,
            "result_id",
            fingerprint_page_projection_identity(
                namespace=self.CONTRACT_NAME,
                material={
                    "contract_version": self.CONTRACT_VERSION,
                    "enrichment_result_id": self.enrichment.result_id,
                    "page_projection_result_id": self.projection.result_id,
                    "publication_id": self.receipt.publication_id,
                    "receipt_id": self.request.expected_receipt_id,
                    "request_id": self.request.request_id,
                },
            ),
        )

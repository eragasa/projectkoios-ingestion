"""Immutable request for sanitized page-projection evidence enrichment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.result import PageProjectionResult


def validate_page_projection_evidence_enrichment_input(
    *, projection: PageProjectionResult
) -> None:
    """Require one fresh exact current page-projection result."""
    if type(projection) is not PageProjectionResult:
        raise TypeError("projection must be PageProjectionResult")
    try:
        fresh = PageProjectionResult(
            request=projection.request,
            pages=projection.pages,
            limitations=projection.limitations,
            reading_evidence_limitations=(
                projection.reading_evidence_limitations
            ),
            processor_id=projection.processor_id,
            processor_version=projection.processor_version,
        )
    except PageProjectionError:
        raise
    except (TypeError, ValueError) as error:
        raise PageProjectionError(
            "page projection enrichment input is stale"
        ) from error
    if fresh != projection:
        raise PageProjectionError(
            "page projection enrichment input identity is stale"
        )


@dataclass(frozen=True, slots=True)
class PageProjectionEvidenceEnrichmentRequest(DataObjectActionRequest):
    """Bind one exact current page projection to enrichment derivation."""

    CONTRACT_NAME: ClassVar[str] = "page-projection-evidence-enrichment-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    projection: PageProjectionResult
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        validate_page_projection_evidence_enrichment_input(
            projection=self.projection
        )
        object.__setattr__(
            self,
            "request_id",
            fingerprint_page_projection_identity(
                namespace=self.CONTRACT_NAME,
                material={
                    "contract_version": self.CONTRACT_VERSION,
                    "page_projection_result_id": self.projection.result_id,
                },
            ),
        )


def validate_page_projection_evidence_enrichment_request(
    *, request: PageProjectionEvidenceEnrichmentRequest
) -> None:
    """Require a fresh request identity for its exact projection input."""
    if type(request) is not PageProjectionEvidenceEnrichmentRequest:
        raise TypeError(
            "request must be PageProjectionEvidenceEnrichmentRequest"
        )
    fresh = PageProjectionEvidenceEnrichmentRequest(
        projection=request.projection
    )
    if fresh != request:
        raise PageProjectionError(
            "page projection enrichment request identity is stale"
        )

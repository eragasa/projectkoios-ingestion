"""Immutable result of page-projection evidence enrichment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.page.projection.enrichment.derivation import (
    derive_page_projection_evidence_enrichments,
)
from projectkoios.ingestion.page.projection.enrichment.inventory import (
    PageProjectionEvidenceEnrichmentInventory,
)
from projectkoios.ingestion.page.projection.enrichment.request import (
    PageProjectionEvidenceEnrichmentRequest,
    validate_page_projection_evidence_enrichment_request,
)
from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)


@dataclass(frozen=True, slots=True)
class PageProjectionEvidenceEnrichmentResult(DataObjectActionResult):
    """Bind one exact page projection to complete sanitized enrichments."""

    CONTRACT_NAME: ClassVar[str] = "page-projection-evidence-enrichment-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    PROCESSOR_ID: ClassVar[str] = (
        "page-projection-evidence-enrichment-actionizer"
    )
    PROCESSOR_VERSION: ClassVar[str] = "1.0"

    request: PageProjectionEvidenceEnrichmentRequest
    entries: PageProjectionEvidenceEnrichmentInventory
    processor_id: str
    processor_version: str
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not PageProjectionEvidenceEnrichmentRequest:
            raise TypeError(
                "request must be PageProjectionEvidenceEnrichmentRequest"
            )
        validate_page_projection_evidence_enrichment_request(
            request=self.request
        )
        if type(self.entries) is not PageProjectionEvidenceEnrichmentInventory:
            raise TypeError(
                "entries must be PageProjectionEvidenceEnrichmentInventory"
            )
        expected = derive_page_projection_evidence_enrichments(
            result=self.request.projection
        )
        if self.entries != expected:
            raise PageProjectionError(
                "enrichment entries differ from deterministic derivation"
            )
        expected_count = self.request.projection.pages.block_count
        if len(self.entries) != expected_count:
            raise PageProjectionError(
                "enrichment entries do not completely cover projected blocks"
            )
        processor_id = PAGE_PROJECTION_LIMITS.require_identity(
            self.processor_id, "processor_id"
        )
        processor_version = PAGE_PROJECTION_LIMITS.require_text(
            self.processor_version,
            "processor_version",
            maximum_bytes=PAGE_PROJECTION_LIMITS.maximum_processor_version_bytes,
        )
        if (
            processor_id != self.PROCESSOR_ID
            or processor_version != self.PROCESSOR_VERSION
        ):
            raise PageProjectionError(
                "enrichment processor identity is unsupported"
            )
        object.__setattr__(
            self,
            "result_id",
            fingerprint_page_projection_identity(
                namespace=self.CONTRACT_NAME,
                material={
                    "contract_version": self.CONTRACT_VERSION,
                    "entry_inventory_id": self.entries.inventory_id,
                    "processor_id": processor_id,
                    "processor_version": processor_version,
                    "request_id": self.request.request_id,
                },
            ),
        )

    @property
    def page_projection_result_id(self) -> str:
        """Return the exact enriched page-projection result identity."""
        return self.request.projection.result_id

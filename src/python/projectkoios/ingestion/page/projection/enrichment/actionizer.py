"""Pure current-schema page-projection evidence enrichment action."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.page.projection.enrichment.derivation import (
    derive_page_projection_evidence_enrichments,
)
from projectkoios.ingestion.page.projection.enrichment.request import (
    PageProjectionEvidenceEnrichmentRequest,
    validate_page_projection_evidence_enrichment_request,
)
from projectkoios.ingestion.page.projection.enrichment.result import (
    PageProjectionEvidenceEnrichmentResult,
)


class PageProjectionEvidenceEnrichmentActionizer(
    DataObjectActionizer[
        PageProjectionEvidenceEnrichmentRequest,
        PageProjectionEvidenceEnrichmentResult,
    ]
):
    """Expose sanitized exact retained evidence without side effects."""

    __slots__ = ()

    def action(
        self,
        *,
        request: PageProjectionEvidenceEnrichmentRequest,
    ) -> PageProjectionEvidenceEnrichmentResult:
        """Return one exact enrichment disposition per projected block."""
        validate_page_projection_evidence_enrichment_request(request=request)
        entries = derive_page_projection_evidence_enrichments(
            result=request.projection
        )
        return PageProjectionEvidenceEnrichmentResult(
            request=request,
            entries=entries,
            processor_id=(PageProjectionEvidenceEnrichmentResult.PROCESSOR_ID),
            processor_version=(
                PageProjectionEvidenceEnrichmentResult.PROCESSOR_VERSION
            ),
        )

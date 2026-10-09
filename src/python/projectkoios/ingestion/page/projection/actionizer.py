"""Pure synchronous current-schema page projector."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.page.projection.limitation import (
    PageProjectionLimitationInventory,
)
from projectkoios.ingestion.page.projection.page import (
    derive_page_projection_pages,
)
from projectkoios.ingestion.page.projection.request import (
    PageProjectionRequest,
    validate_page_projection_request_freshness,
)
from projectkoios.ingestion.page.projection.result import (
    PageProjectionResult,
)


class PageProjectionActionizer(
    DataObjectActionizer[PageProjectionRequest, PageProjectionResult]
):
    """Project verified canonical reading evidence without side effects."""

    def action(self, *, request: PageProjectionRequest) -> PageProjectionResult:
        """Return deterministic citation-aligned text-only pages."""
        if type(request) is not PageProjectionRequest:
            raise TypeError("request must be PageProjectionRequest")
        validate_page_projection_request_freshness(request=request)
        pages = derive_page_projection_pages(
            document=request.source_result.document,
            include_figure_captions=request.include_figure_captions,
        )
        return PageProjectionResult(
            request=request,
            pages=pages,
            limitations=PageProjectionLimitationInventory(),
            reading_evidence_limitations=(
                request.source_result.document.limitations
            ),
            processor_id=PageProjectionResult.PROCESSOR_ID,
            processor_version=PageProjectionResult.PROCESSOR_VERSION,
        )

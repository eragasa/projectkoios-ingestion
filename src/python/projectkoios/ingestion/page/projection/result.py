"""Immutable result of pure current-schema page projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.identity import (
    PageProjectionResultIdentityDerivation,
)
from projectkoios.ingestion.page.projection.limitation import (
    PageProjectionLimitationInventory,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)
from projectkoios.ingestion.page.projection.page import (
    PageProjectionPageInventory,
    derive_page_projection_pages,
)
from projectkoios.ingestion.page.projection.request import (
    PageProjectionRequest,
    validate_page_projection_request_freshness,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.inventory import (  # noqa: E501
    ReadingEvidenceLimitationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.identity import (  # noqa: E501
    ReadingEvidenceProjectionIdentityDerivation,
)


@dataclass(frozen=True, slots=True)
class PageProjectionResult(DataObjectActionResult):
    """Bind exact input evidence to text-only citation-aligned pages."""

    CONTRACT_NAME: ClassVar[str] = "page-projection-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    PROCESSOR_ID: ClassVar[str] = "page-projection-actionizer"
    PROCESSOR_VERSION: ClassVar[str] = "1.0"

    request: PageProjectionRequest
    pages: PageProjectionPageInventory
    limitations: PageProjectionLimitationInventory
    reading_evidence_limitations: ReadingEvidenceLimitationInventory
    processor_id: str
    processor_version: str
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not PageProjectionRequest:
            raise TypeError("request must be PageProjectionRequest")
        validate_page_projection_request_freshness(request=self.request)
        if type(self.pages) is not PageProjectionPageInventory:
            raise TypeError("pages must be PageProjectionPageInventory")
        expected_pages = derive_page_projection_pages(
            document=self.request.source_result.document,
            include_figure_captions=(self.request.include_figure_captions),
        )
        if self.pages != expected_pages:
            raise PageProjectionError(
                "result pages differ from deterministic projection"
            )
        if (
            len(self.pages) != len(self.request.source_result.document.pages)
            or next(iter(self.pages)).physical_page_index != 0
        ):
            raise PageProjectionError(
                "result pages do not completely cover the document"
            )
        if type(self.limitations) is not PageProjectionLimitationInventory:
            raise TypeError(
                "limitations must be PageProjectionLimitationInventory"
            )
        if self.limitations != PageProjectionLimitationInventory():
            raise PageProjectionError(
                "page projection limitations are incomplete"
            )
        if (
            type(self.reading_evidence_limitations)
            is not ReadingEvidenceLimitationInventory
        ):
            raise TypeError(
                "reading_evidence_limitations has an unsupported type"
            )
        if (
            self.reading_evidence_limitations
            != self.request.source_result.document.limitations
        ):
            raise PageProjectionError(
                "reading evidence limitations differ from the document"
            )
        processor_id = PAGE_PROJECTION_LIMITS.require_identity(
            self.processor_id,
            "processor_id",
        )
        processor_version = PAGE_PROJECTION_LIMITS.require_text(
            self.processor_version,
            "processor_version",
            maximum_bytes=(
                PAGE_PROJECTION_LIMITS.maximum_processor_version_bytes
            ),
        )
        if (
            processor_id != self.PROCESSOR_ID
            or processor_version != self.PROCESSOR_VERSION
        ):
            raise PageProjectionError(
                "page projection processor identity is unsupported"
            )
        reading_limitation_inventory_id = (
            ReadingEvidenceProjectionIdentityDerivation.derive_inventory(
                role="limitations",
                identities=(
                    self.reading_evidence_limitations.identity_material()
                ),
            )
        )
        object.__setattr__(
            self,
            "result_id",
            PageProjectionResultIdentityDerivation.derive(
                request_id=self.request.request_id,
                source_id=self.request.source_result.document.source_id.value,
                page_inventory_id=self.pages.inventory_id,
                limitation_inventory_id=self.limitations.inventory_id,
                reading_limitation_inventory_id=(
                    reading_limitation_inventory_id.value
                ),
                processor_id=processor_id,
                processor_version=processor_version,
                contract_version=self.CONTRACT_VERSION,
            ),
        )

    @property
    def document_id(self) -> ReadingEvidenceIdentity:
        """Return the exact canonical reading-document identity."""
        return self.request.source_result.document.document_id

    @property
    def source_id(self) -> ReadingEvidenceIdentity:
        """Return the exact source identity."""
        return self.request.source_result.document.source_id

    @property
    def projection_result_id(self) -> ReadingEvidenceIdentity:
        """Return the exact upstream reading-projection identity."""
        return self.request.source_result.projection_result_id

    @property
    def reading_inventory_id(self) -> ReadingEvidenceIdentity:
        """Return the exact upstream reading-inventory identity."""
        return self.request.source_result.inventory.inventory_id

    @property
    def source_result_id(self) -> str:
        """Return the exact upstream source-result identity."""
        return self.request.source_result.result_id

    @property
    def artifact_verification_result_id(self) -> str:
        """Return the exact managed-artifact verification identity."""
        return self.request.artifact_verification_result.result_id

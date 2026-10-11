"""Complete private current-schema evidence for one publication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.page.projection.enrichment.result import (
    PageProjectionEvidenceEnrichmentResult,
)
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)
from projectkoios.ingestion.page.projection.publication.code import (
    PageProjectionPublicationCodeInventory,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class PageProjectionPublicationEvidence:
    """Bind fresh extraction evidence to nested B/A/source evidence."""

    CONTRACT_NAME: ClassVar[str] = "page-projection-publication-evidence"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    extraction_manifest_id: str
    extracted_document_id: str
    extraction_warning_count: int
    extraction_warning_codes: PageProjectionPublicationCodeInventory
    enrichment: PageProjectionEvidenceEnrichmentResult

    def __post_init__(self) -> None:
        for value, name in (
            (self.extraction_manifest_id, "extraction_manifest_id"),
            (self.extracted_document_id, "extracted_document_id"),
        ):
            PAGE_PROJECTION_LIMITS.require_identity(value, name)
        if (
            type(self.extraction_warning_count) is not int
            or self.extraction_warning_count < 0
        ):
            raise ValueError("extraction_warning_count is invalid")
        if (
            type(self.extraction_warning_codes)
            is not PageProjectionPublicationCodeInventory
        ):
            raise TypeError("extraction_warning_codes has an unsupported type")
        if type(self.enrichment) is not PageProjectionEvidenceEnrichmentResult:
            raise TypeError("enrichment has an unsupported type")
        document = (
            self.enrichment.request.projection.request.source_result.document
        )
        if (
            document.producer_evidence.extraction_result_id.value
            != self.extraction_manifest_id
            or document.producer_evidence.document_id.value
            != self.extracted_document_id
        ):
            raise ValueError("extraction evidence differs from current source")

    def payload_bytes(self) -> bytes:
        """Serialize the exact private nested current evidence canonically."""
        return CanonicalJsonSerializer.serialize_bytes(
            {
                "contract_name": self.CONTRACT_NAME,
                "contract_version": self.CONTRACT_VERSION,
                "enrichment": self.enrichment,
                "extracted_document_id": self.extracted_document_id,
                "extraction_manifest_id": self.extraction_manifest_id,
                "extraction_warning_count": self.extraction_warning_count,
                "extraction_warning_codes": (
                    self.extraction_warning_codes.values()
                ),
            }
        )

    def payload_sha256(self) -> SHA256Hash:
        """Return the exact canonical private payload digest."""
        return SHA256Fingerprinter.fingerprint(content=self.payload_bytes())

    def payload_id(self) -> str:
        """Return the content-addressed private evidence identity."""
        return fingerprint_page_projection_identity(
            namespace="page-projection-publication-payload",
            material={
                "contract_version": self.CONTRACT_VERSION,
                "payload_sha256": self.payload_sha256(),
            },
        )

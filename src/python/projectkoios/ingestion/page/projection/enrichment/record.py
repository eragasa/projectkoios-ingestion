"""Available and explicitly unavailable page-projection enrichments."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.page.projection.enrichment.basis import (
    PageProjectionEvidenceRetainedTextBasis,
    PageProjectionEvidenceUnavailableReason,
)
from projectkoios.ingestion.page.projection.enrichment.binding import (
    PageProjectionEvidenceCrossBinding,
)
from projectkoios.ingestion.page.projection.enrichment.identity import (
    PageProjectionEvidenceIdentityInventory,
)
from projectkoios.ingestion.page.projection.enrichment.limitation import (
    PageProjectionEvidenceLimitationInventory,
)
from projectkoios.ingestion.page.projection.enrichment.producer import (
    PageProjectionEvidenceProducerBindingInventory,
)
from projectkoios.ingestion.page.projection.enrichment.warning import (
    PageProjectionEvidenceWarningInventory,
)
from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


@dataclass(frozen=True, slots=True)
class PageProjectionEvidenceEnrichment:
    """Expose exact raw text and provenance for a paragraph or heading."""

    binding: PageProjectionEvidenceCrossBinding
    retained_text: str
    retained_text_basis: PageProjectionEvidenceRetainedTextBasis
    producers: PageProjectionEvidenceProducerBindingInventory
    source_span_ids: PageProjectionEvidenceIdentityInventory
    warnings: PageProjectionEvidenceWarningInventory
    limitations: PageProjectionEvidenceLimitationInventory
    retained_text_sha256: str = field(init=False)
    enrichment_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.binding) is not PageProjectionEvidenceCrossBinding:
            raise TypeError(
                "binding must be PageProjectionEvidenceCrossBinding"
            )
        retained_text = PAGE_PROJECTION_LIMITS.require_text(
            self.retained_text,
            "retained_text",
            maximum_bytes=(
                PAGE_PROJECTION_LIMITS.maximum_enrichment_retained_text_bytes
            ),
        )
        expected_basis = PageProjectionEvidenceRetainedTextBasis(
            "text_block_raw_source_sequence"
        )
        if self.retained_text_basis is not expected_basis:
            raise PageProjectionError("retained text basis is unsupported")
        if (
            type(self.producers)
            is not PageProjectionEvidenceProducerBindingInventory
        ):
            raise TypeError("producers has an unsupported type")
        if (
            type(self.source_span_ids)
            is not PageProjectionEvidenceIdentityInventory
            or not self.source_span_ids
        ):
            raise PageProjectionError("enrichment requires source spans")
        if type(self.warnings) is not PageProjectionEvidenceWarningInventory:
            raise TypeError("warnings has an unsupported type")
        if (
            type(self.limitations)
            is not PageProjectionEvidenceLimitationInventory
        ):
            raise TypeError("limitations has an unsupported type")
        digest = SHA256Fingerprinter.fingerprint(
            content=retained_text.encode("utf-8", errors="strict")
        )
        object.__setattr__(self, "retained_text_sha256", digest)
        object.__setattr__(
            self,
            "enrichment_id",
            fingerprint_page_projection_identity(
                namespace="page-projection-evidence-enrichment",
                material={
                    "binding_id": self.binding.binding_id,
                    "limitation_inventory_id": self.limitations.inventory_id,
                    "producer_inventory_id": self.producers.inventory_id,
                    "retained_text_basis": self.retained_text_basis.value,
                    "retained_text_sha256": digest,
                    "source_span_inventory_id": (
                        self.source_span_ids.inventory_id
                    ),
                    "warning_inventory_id": self.warnings.inventory_id,
                },
            ),
        )

    @property
    def source_evidence_id(self) -> str:
        """Return the exact downstream join key."""
        return self.binding.source_evidence_id

    @property
    def page_projection_block_id(self) -> str:
        """Return the exact projected block identity."""
        return self.binding.page_projection_block_id

    @property
    def page_projection_page_id(self) -> str:
        """Return the exact projected page identity."""
        return self.binding.page_projection_page_id

    @property
    def entry_id(self) -> str:
        """Return the immutable enrichment identity."""
        return self.enrichment_id


@dataclass(frozen=True, slots=True)
class PageProjectionEvidenceUnavailable:
    """Preserve one projected key that cannot be enriched without invention."""

    binding: PageProjectionEvidenceCrossBinding
    reason: PageProjectionEvidenceUnavailableReason
    producer_record_ids: PageProjectionEvidenceIdentityInventory
    limitations: PageProjectionEvidenceLimitationInventory
    disposition_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.binding) is not PageProjectionEvidenceCrossBinding:
            raise TypeError(
                "binding must be PageProjectionEvidenceCrossBinding"
            )
        if not isinstance(self.reason, PageProjectionEvidenceUnavailableReason):
            raise TypeError("unavailable reason has an unsupported type")
        if (
            type(self.producer_record_ids)
            is not PageProjectionEvidenceIdentityInventory
            or not self.producer_record_ids
        ):
            raise PageProjectionError(
                "unavailable evidence requires producer record identities"
            )
        if (
            type(self.limitations)
            is not PageProjectionEvidenceLimitationInventory
        ):
            raise TypeError("limitations has an unsupported type")
        object.__setattr__(
            self,
            "disposition_id",
            fingerprint_page_projection_identity(
                namespace="page-projection-evidence-unavailable",
                material={
                    "binding_id": self.binding.binding_id,
                    "limitation_inventory_id": self.limitations.inventory_id,
                    "producer_record_inventory_id": (
                        self.producer_record_ids.inventory_id
                    ),
                    "reason": self.reason.value,
                },
            ),
        )

    @property
    def source_evidence_id(self) -> str:
        """Return the exact downstream join key."""
        return self.binding.source_evidence_id

    @property
    def page_projection_block_id(self) -> str:
        """Return the exact projected block identity."""
        return self.binding.page_projection_block_id

    @property
    def page_projection_page_id(self) -> str:
        """Return the exact projected page identity."""
        return self.binding.page_projection_page_id

    @property
    def entry_id(self) -> str:
        """Return the immutable unavailable-disposition identity."""
        return self.disposition_id


type PageProjectionEvidenceEntry = (
    PageProjectionEvidenceEnrichment | PageProjectionEvidenceUnavailable
)

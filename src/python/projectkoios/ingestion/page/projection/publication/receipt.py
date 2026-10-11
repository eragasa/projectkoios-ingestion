"""Transport-safe immutable authority receipt for one publication."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)
from projectkoios.ingestion.page.projection.publication.code import (
    PageProjectionPublicationCodeInventory,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class PageProjectionPublicationReceipt(AbstractImmutableDataObject):
    """Retain safe scalar identities and measures, never payload or paths."""

    CONTRACT_NAME: ClassVar[str] = "page-projection-publication-receipt"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    pipeline_configuration_id: str
    source_artifact_id: str
    source_sha256: SHA256Hash
    source_byte_length: int
    source_media_type: str
    artifact_verification_result_id: str
    extraction_manifest_id: str
    extracted_document_id: str
    reading_source_id: str
    reading_document_id: str
    reading_projection_result_id: str
    reading_inventory_id: str
    reading_source_result_id: str
    page_projection_result_id: str
    page_projection_inventory_id: str
    enrichment_result_id: str
    enrichment_inventory_id: str
    page_count: int
    block_count: int
    enrichment_available_count: int
    enrichment_unavailable_count: int
    extraction_warning_count: int
    extraction_warning_codes: PageProjectionPublicationCodeInventory
    reading_limitation_count: int
    reading_limitation_codes: PageProjectionPublicationCodeInventory
    page_projection_limitation_count: int
    page_projection_limitation_codes: PageProjectionPublicationCodeInventory
    payload_id: str
    payload_sha256: SHA256Hash
    payload_byte_length: int
    publication_id: str = field(init=False)

    def __post_init__(self) -> None:
        identity_fields = (
            "pipeline_configuration_id",
            "source_artifact_id",
            "artifact_verification_result_id",
            "extraction_manifest_id",
            "extracted_document_id",
            "reading_source_id",
            "reading_document_id",
            "reading_projection_result_id",
            "reading_inventory_id",
            "reading_source_result_id",
            "page_projection_result_id",
            "page_projection_inventory_id",
            "enrichment_result_id",
            "enrichment_inventory_id",
            "payload_id",
        )
        for name in identity_fields:
            PAGE_PROJECTION_LIMITS.require_identity(getattr(self, name), name)
        source_digest = SHA256Hash(self.source_sha256)
        payload_digest = SHA256Hash(self.payload_sha256)
        if self.source_media_type != ManagedArtifactMediaType.APPLICATION_PDF:
            raise ValueError("source_media_type must be application/pdf")
        counts = (
            (self.source_byte_length, "source_byte_length", True),
            (self.page_count, "page_count", True),
            (self.block_count, "block_count", False),
            (
                self.enrichment_available_count,
                "enrichment_available_count",
                False,
            ),
            (
                self.enrichment_unavailable_count,
                "enrichment_unavailable_count",
                False,
            ),
            (
                self.extraction_warning_count,
                "extraction_warning_count",
                False,
            ),
            (
                self.reading_limitation_count,
                "reading_limitation_count",
                False,
            ),
            (
                self.page_projection_limitation_count,
                "page_projection_limitation_count",
                False,
            ),
            (self.payload_byte_length, "payload_byte_length", True),
        )
        for value, name, positive in counts:
            minimum = 1 if positive else 0
            if type(value) is not int or value < minimum:
                raise ValueError(f"{name} is invalid")
        if (
            self.enrichment_available_count + self.enrichment_unavailable_count
            != self.block_count
        ):
            raise ValueError("enrichment counts do not cover all blocks")
        code_inventories = (
            (
                self.extraction_warning_codes,
                self.extraction_warning_count,
                "extraction_warning_codes",
            ),
            (
                self.reading_limitation_codes,
                self.reading_limitation_count,
                "reading_limitation_codes",
            ),
            (
                self.page_projection_limitation_codes,
                self.page_projection_limitation_count,
                "page_projection_limitation_codes",
            ),
        )
        for inventory, count, name in code_inventories:
            if type(inventory) is not PageProjectionPublicationCodeInventory:
                raise TypeError(f"{name} has an unsupported type")
            if len(inventory) > count:
                raise ValueError(f"{name} exceeds its evidence count")
        object.__setattr__(self, "source_sha256", source_digest)
        object.__setattr__(self, "payload_sha256", payload_digest)
        object.__setattr__(
            self,
            "publication_id",
            fingerprint_page_projection_identity(
                namespace="page-projection-publication",
                material={
                    "contract_version": self.CONTRACT_VERSION,
                    "payload_id": self.payload_id,
                    "payload_sha256": payload_digest,
                    "pipeline_configuration_id": (
                        self.pipeline_configuration_id
                    ),
                    "source_artifact_id": self.source_artifact_id,
                },
            ),
        )

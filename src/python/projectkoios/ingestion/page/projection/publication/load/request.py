"""Immutable request for one exact typed publication load."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class PageProjectionPublicationLoadRequest(DataObjectActionRequest):
    """Bind all immutable identities needed to load one exact publication."""

    CONTRACT_NAME: ClassVar[str] = "page-projection-publication-load-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    source_artifact: ManagedArtifactReference
    expected_pipeline_configuration_id: str
    expected_publication_id: str
    expected_receipt_id: str
    expected_receipt_sha256: SHA256Hash
    expected_receipt_byte_length: int
    expected_payload_id: str
    expected_payload_sha256: SHA256Hash
    expected_payload_byte_length: int
    expected_page_projection_result_id: str
    expected_enrichment_result_id: str
    maximum_payload_bytes: int
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.source_artifact) is not ManagedArtifactReference:
            raise TypeError("source_artifact must be ManagedArtifactReference")
        identities = (
            (
                self.expected_pipeline_configuration_id,
                "expected_pipeline_configuration_id",
                "page-projection-publication-pipeline:sha256:",
            ),
            (
                self.expected_publication_id,
                "expected_publication_id",
                "page-projection-publication:sha256:",
            ),
            (
                self.expected_receipt_id,
                "expected_receipt_id",
                "page-projection-publication-receipt:sha256:",
            ),
            (
                self.expected_payload_id,
                "expected_payload_id",
                "page-projection-publication-payload:sha256:",
            ),
            (
                self.expected_page_projection_result_id,
                "expected_page_projection_result_id",
                "page-projection-result:sha256:",
            ),
            (
                self.expected_enrichment_result_id,
                "expected_enrichment_result_id",
                "page-projection-evidence-enrichment-result:sha256:",
            ),
        )
        material: dict[str, object] = {
            "contract_version": self.CONTRACT_VERSION,
            "source_artifact_id": self.source_artifact.artifact_id,
        }
        for identity_value, name, prefix in identities:
            checked = PAGE_PROJECTION_LIMITS.require_identity(
                identity_value, name
            )
            if not checked.startswith(prefix):
                raise ValueError(f"{name} has the wrong role")
            material[name] = checked
        for digest_value, name in (
            (self.expected_receipt_sha256, "expected_receipt_sha256"),
            (self.expected_payload_sha256, "expected_payload_sha256"),
        ):
            if not isinstance(digest_value, SHA256Hash):
                raise TypeError(f"{name} must be SHA256Hash")
            material[name] = digest_value
        if self.expected_receipt_id != (
            "page-projection-publication-receipt:sha256:"
            + self.expected_receipt_sha256
        ):
            raise ValueError(
                "expected receipt identity differs from its digest"
            )
        bounds = (
            (
                self.expected_receipt_byte_length,
                1_000_000,
                "expected_receipt_byte_length",
            ),
            (
                self.expected_payload_byte_length,
                1_000_000_000,
                "expected_payload_byte_length",
            ),
            (
                self.maximum_payload_bytes,
                1_000_000_000,
                "maximum_payload_bytes",
            ),
        )
        for bound_value, maximum, name in bounds:
            if type(bound_value) is not int or not 1 <= bound_value <= maximum:
                raise ValueError(f"{name} is outside its supported bound")
            material[name] = bound_value
        if self.expected_payload_byte_length > self.maximum_payload_bytes:
            raise ValueError("expected payload exceeds its declared ceiling")
        object.__setattr__(
            self,
            "request_id",
            fingerprint_page_projection_identity(
                namespace=self.CONTRACT_NAME,
                material=material,
            ),
        )

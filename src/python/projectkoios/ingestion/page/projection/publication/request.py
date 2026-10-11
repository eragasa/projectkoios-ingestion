"""Owner-native request for one durable page-projection publication."""

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
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)


@dataclass(frozen=True, slots=True)
class PageProjectionPublicationRequest(DataObjectActionRequest):
    """Request one exact artifact publication with narrowing bounds and CAS."""

    CONTRACT_NAME: ClassVar[str] = "page-projection-publication-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    source_artifact: ManagedArtifactReference
    expected_pipeline_configuration_id: str
    maximum_page_count: int
    maximum_block_count: int
    idempotency_token: str
    expected_current_publication_id: str | None
    request_fingerprint: str = field(init=False)
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.source_artifact) is not ManagedArtifactReference:
            raise TypeError("source_artifact must be ManagedArtifactReference")
        pipeline_id = PAGE_PROJECTION_LIMITS.require_identity(
            self.expected_pipeline_configuration_id,
            "expected_pipeline_configuration_id",
        )
        if not pipeline_id.startswith(
            "page-projection-publication-pipeline:sha256:"
        ):
            raise ValueError(
                "expected_pipeline_configuration_id has the wrong role"
            )
        bounds = (
            (
                self.maximum_page_count,
                min(
                    READING_EVIDENCE_LIMITS.maximum_pages,
                    PAGE_PROJECTION_LIMITS.maximum_pages,
                ),
                "maximum_page_count",
            ),
            (
                self.maximum_block_count,
                min(
                    READING_EVIDENCE_LIMITS.maximum_blocks,
                    PAGE_PROJECTION_LIMITS.maximum_blocks,
                ),
                "maximum_block_count",
            ),
        )
        for value, maximum, name in bounds:
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"{name} is outside its supported bound")
        if (
            type(self.idempotency_token) is not str
            or not self.idempotency_token
        ):
            raise ValueError("idempotency_token must be non-empty")
        if len(self.idempotency_token.encode("utf-8", errors="strict")) > 256:
            raise ValueError("idempotency_token exceeds its limit")
        current_id = self.expected_current_publication_id
        if current_id is not None:
            current_id = PAGE_PROJECTION_LIMITS.require_identity(
                current_id,
                "expected_current_publication_id",
            )
            if not current_id.startswith("page-projection-publication:sha256:"):
                raise ValueError(
                    "expected_current_publication_id has the wrong role"
                )
        fingerprint = fingerprint_page_projection_identity(
            namespace="page-projection-publication-request-fingerprint",
            material={
                "contract_version": self.CONTRACT_VERSION,
                "expected_current_publication_id": current_id,
                "expected_pipeline_configuration_id": pipeline_id,
                "maximum_block_count": self.maximum_block_count,
                "maximum_page_count": self.maximum_page_count,
                "source_artifact_id": self.source_artifact.artifact_id,
            },
        )
        object.__setattr__(
            self, "expected_pipeline_configuration_id", pipeline_id
        )
        object.__setattr__(self, "expected_current_publication_id", current_id)
        object.__setattr__(self, "request_fingerprint", fingerprint)
        object.__setattr__(
            self,
            "request_id",
            fingerprint_page_projection_identity(
                namespace=self.CONTRACT_NAME,
                material={
                    "idempotency_token": self.idempotency_token,
                    "request_fingerprint": fingerprint,
                },
            ),
        )

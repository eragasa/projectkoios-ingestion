"""Owner-native request for one current page-projection publication."""

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


@dataclass(frozen=True, slots=True)
class PageProjectionPublicationReadRequest(DataObjectActionRequest):
    """Select one locator-free managed artifact publication subject."""

    CONTRACT_NAME: ClassVar[str] = "page-projection-publication-read-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    source_artifact: ManagedArtifactReference
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.source_artifact) is not ManagedArtifactReference:
            raise TypeError("source_artifact must be ManagedArtifactReference")
        object.__setattr__(
            self,
            "request_id",
            fingerprint_page_projection_identity(
                namespace=self.CONTRACT_NAME,
                material={
                    "contract_version": self.CONTRACT_VERSION,
                    "source_artifact_id": self.source_artifact.artifact_id,
                },
            ),
        )

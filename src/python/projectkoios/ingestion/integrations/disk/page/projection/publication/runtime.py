"""Trusted disk runtime composition for page-projection publication."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from projectkoios.ingestion.integrations.disk.artifact.managed.binding import (
    DiskManagedArtifactBindingInventory,
)
from projectkoios.ingestion.integrations.disk.artifact.managed.provider import (
    DiskManagedArtifactByteProvider,
)
from projectkoios.ingestion.integrations.disk.page.projection.publication.store import (  # noqa: E501
    DiskPageProjectionPublicationStore,
)
from projectkoios.ingestion.page.projection.publication.actionizer import (
    PageProjectionPublicationActionizer,
)
from projectkoios.ingestion.page.projection.publication.configuration import (
    PageProjectionPublicationConfiguration,
)
from projectkoios.ingestion.page.projection.publication.read.actionizer import (
    PageProjectionPublicationReadActionizer,
)


@dataclass(frozen=True, slots=True)
class DiskPageProjectionPublicationRuntime:
    """Hold only trusted server-side roots, bindings, scope, and ceilings."""

    source_root: Path
    source_bindings: DiskManagedArtifactBindingInventory
    publication_root: Path
    deployment_scope_id: str
    configuration: PageProjectionPublicationConfiguration

    def __post_init__(self) -> None:
        if not isinstance(self.source_root, Path):
            raise TypeError("source_root must be a Path")
        if (
            type(self.source_bindings)
            is not DiskManagedArtifactBindingInventory
        ):
            raise TypeError("source_bindings has an unsupported type")
        if not isinstance(self.publication_root, Path):
            raise TypeError("publication_root must be a Path")
        if (
            type(self.deployment_scope_id) is not str
            or not self.deployment_scope_id
        ):
            raise ValueError("deployment_scope_id must be non-empty")
        if (
            type(self.configuration)
            is not PageProjectionPublicationConfiguration
        ):
            raise TypeError("configuration has an unsupported type")

    def create_actionizer(self) -> PageProjectionPublicationActionizer:
        """Compose the exact owner action from trusted server capabilities."""
        provider = DiskManagedArtifactByteProvider(
            root=self.source_root,
            bindings=self.source_bindings,
            authority_id=self.configuration.authority_id,
        )
        store = DiskPageProjectionPublicationStore(
            root=self.publication_root,
            deployment_scope_id=self.deployment_scope_id,
        )
        return PageProjectionPublicationActionizer(
            provider=provider,
            store=store,
            configuration=self.configuration,
        )

    def create_read_actionizer(
        self,
    ) -> PageProjectionPublicationReadActionizer:
        """Compose the pure current-publication read from trusted storage."""
        store = DiskPageProjectionPublicationStore(
            root=self.publication_root,
            deployment_scope_id=self.deployment_scope_id,
        )
        return PageProjectionPublicationReadActionizer(store=store)

"""Explicit private-root composition for exact typed publication loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from projectkoios.ingestion.integrations.disk.page.projection.publication.load.source import (  # noqa: E501
    DiskPageProjectionPublicationPayloadSource,
)
from projectkoios.ingestion.page.projection.publication.load.actionizer import (
    PageProjectionPublicationLoadActionizer,
)


@dataclass(frozen=True, slots=True)
class DiskPageProjectionPublicationLoadRuntime:
    """Hold one operational root outside semantic publication identities."""

    publication_root: Path

    def __post_init__(self) -> None:
        if not isinstance(self.publication_root, Path):
            raise TypeError("publication_root must be a Path")

    def create_actionizer(self) -> PageProjectionPublicationLoadActionizer:
        """Compose one read-only exact typed loader."""
        return PageProjectionPublicationLoadActionizer(
            source=DiskPageProjectionPublicationPayloadSource(
                root=self.publication_root
            )
        )

"""Backend-neutral source port for transient managed-artifact bytes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import AbstractContextManager

from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)


class ManagedArtifactByteProvider(ABC):
    """Resolve exact locator-free references into bounded transient chunks."""

    @property
    @abstractmethod
    def implementation_id(self) -> str:
        """Identify the concrete provider implementation and version."""

    @abstractmethod
    def open_chunks(
        self,
        *,
        reference: ManagedArtifactReference,
        authority_id: str,
        maximum_bytes: int,
        chunk_bytes: int,
    ) -> AbstractContextManager[Iterator[bytes]]:
        """Open bounded ordered bytes with deterministic resource release."""

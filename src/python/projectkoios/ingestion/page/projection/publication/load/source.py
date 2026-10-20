"""Read-only source port for exact immutable publication objects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from projectkoios.ingestion.page.projection.publication.load.request import (
    PageProjectionPublicationLoadRequest,
)


@dataclass(frozen=True, slots=True)
class PageProjectionPublicationLoadBytes:
    """Carry exact receipt and private payload bytes across the source port."""

    receipt: bytes
    payload: bytes

    def __post_init__(self) -> None:
        if type(self.receipt) is not bytes or not self.receipt:
            raise ValueError("receipt bytes must be non-empty")
        if type(self.payload) is not bytes or not self.payload:
            raise ValueError("payload bytes must be non-empty")


class PageProjectionPublicationPayloadSource(ABC):
    """Load immutable objects without consulting mutable subject authority."""

    @abstractmethod
    def load(
        self,
        *,
        request: PageProjectionPublicationLoadRequest,
    ) -> PageProjectionPublicationLoadBytes:
        """Return exact content-addressed receipt and payload bytes."""

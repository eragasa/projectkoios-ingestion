"""Backend-neutral extraction publication boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)
from projectkoios.ingestion.storage.extraction.publication.result import (
    ExtractionPublicationResult,
)


class AbstractExtractionPublicationStore(ABC):
    """Durably publish exact extraction decompositions create-once."""

    __slots__ = ()

    @abstractmethod
    def publish(
        self,
        *,
        request: ExtractionPublicationRequest,
    ) -> ExtractionPublicationResult:
        """Commit one publication or return its exact prior commit."""

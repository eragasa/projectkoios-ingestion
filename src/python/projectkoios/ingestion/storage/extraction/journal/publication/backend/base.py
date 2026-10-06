"""Nominal backend port for authoritative extraction journal publication."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.storage.extraction.publication.record import (
    ExtractionPublicationRecord,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)
from projectkoios.ingestion.storage.extraction.publication.result import (
    ExtractionPublicationResult,
)


class ValidatedExtractionJournalPublicationBackend(ABC):
    """Publish one exact extraction request to one configured disk journal."""

    @abstractmethod
    def publish_validated(
        self,
        *,
        journal_reference: str,
        authority_id: str,
        request: ExtractionPublicationRequest,
    ) -> tuple[ExtractionPublicationResult, ExtractionPublicationRecord]:
        """Create or replay one authoritative record."""

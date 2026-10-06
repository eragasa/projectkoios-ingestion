"""Nominal backend port for extraction projection index readiness."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.index.readiness.configuration import (  # noqa: E501
    ExtractionProjectionIndexReadinessConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.index.readiness.evidence.model import (  # noqa: E501
    ExtractionProjectionIndexReadinessEvidence,
)


class ExtractionProjectionIndexReadinessBackend(ABC):
    """Ensure and observe required indexes on one explicit target."""

    @abstractmethod
    def ensure_index_readiness(
        self,
        *,
        target: ExtractionProjectionTargetIdentity,
        configuration: ExtractionProjectionIndexReadinessConfiguration,
        authority_id: str,
    ) -> ExtractionProjectionIndexReadinessEvidence:
        """Return exact evidence after ensuring every configured index."""

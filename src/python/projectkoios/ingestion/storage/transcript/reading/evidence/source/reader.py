"""Backend-neutral reading-evidence read-model reader port."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.storage.transcript.reading.evidence.projection.read.model import (  # noqa: E501
    ReadingEvidenceReadModel,
)
from projectkoios.ingestion.transcript.reading.evidence.source.request import (
    ReadingEvidenceSourceRequest,
)


class ReadingEvidenceReadModelReader(ABC):
    """Read one exact completed storage read model through a provider."""

    __slots__ = ()

    @property
    @abstractmethod
    def implementation_id(self) -> str:
        """Return the exact concrete reader implementation identity."""

    @abstractmethod
    def read(
        self, *, request: ReadingEvidenceSourceRequest
    ) -> ReadingEvidenceReadModel:
        """Return one bounded completed backend-neutral read model."""

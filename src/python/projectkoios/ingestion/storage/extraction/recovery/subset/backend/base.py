"""Nominal backend port for extraction projection subset recovery."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.storage.extraction.recovery.subset.evidence import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryEvidence,
)
from projectkoios.ingestion.storage.extraction.recovery.subset.request import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryRequest,
)


class ExtractionProjectionSubsetRecoveryBackend(ABC):
    """Apply one exact identity filter to an authoritative journal."""

    @abstractmethod
    def recover_subset(
        self,
        *,
        request: ExtractionProjectionSubsetRecoveryRequest,
    ) -> ExtractionProjectionSubsetRecoveryEvidence:
        """Recover exactly the bound record subset or raise a typed error."""

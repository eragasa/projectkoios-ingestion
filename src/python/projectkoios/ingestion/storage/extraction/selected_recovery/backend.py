"""Nominal backend port for selected extraction projection recovery."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.storage.extraction.selected_recovery.evidence import (  # noqa: E501
    SelectedExtractionProjectionRecoveryEvidence,
)
from projectkoios.ingestion.storage.extraction.selected_recovery.request import (  # noqa: E501
    SelectedExtractionProjectionRecoveryRequest,
)


class SelectedExtractionProjectionRecoveryBackend(ABC):
    """Apply one exact identity filter to an authoritative journal."""

    @abstractmethod
    def recover_selected(
        self,
        *,
        request: SelectedExtractionProjectionRecoveryRequest,
    ) -> SelectedExtractionProjectionRecoveryEvidence:
        """Recover all and only selected records or raise a typed error."""

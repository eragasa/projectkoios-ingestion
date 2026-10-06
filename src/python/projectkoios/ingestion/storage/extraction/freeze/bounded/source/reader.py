"""Nominal private-source reader for bounded extraction freezing."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.storage.extraction.freeze.bounded.source.model import (  # noqa: E501
    ExtractionSourceMaterial,
)


class ExtractionSourceReader(ABC):
    """Resolve one opaque source reference under explicit read authority."""

    @abstractmethod
    def read_source(
        self,
        *,
        source_reference: str,
        authority_id: str,
        maximum_bytes: int,
    ) -> ExtractionSourceMaterial:
        """Return exact bytes and locator or raise a typed reader error."""

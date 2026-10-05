"""Nominal extractor boundary for create-once extraction freezing."""

from __future__ import annotations

from abc import abstractmethod

from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.source_extractor import SourceExtractor


class FreezableSourceExtractor(SourceExtractor):
    """Source extractor exposing exact configuration and cache identities."""

    @property
    @abstractmethod
    def extraction_version(self) -> str:
        """Return the exact backend version recorded in extraction manifests."""

    @property
    @abstractmethod
    def configuration_digest(self) -> str:
        """Return the exact extraction configuration digest."""

    @abstractmethod
    def cache_key(self, source: SourceDocument) -> str:
        """Return the cache identity extraction will record for this source."""

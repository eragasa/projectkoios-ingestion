"""Nominal extractor boundary for create-once extraction freezing."""

from __future__ import annotations

from abc import abstractmethod
from typing import BinaryIO, final

from projectkoios.ingestion.models import ExtractionResult, SourceDocument
from projectkoios.ingestion.source_extractor import SourceExtractor
from projectkoios.ingestion.storage.extraction.bounded_freeze.extraction_error import (  # noqa: E501
    FreezableSourceExtractionError,
)


class FreezableSourceExtractor(SourceExtractor):
    """Source extractor exposing exact configuration and cache identities."""

    @final
    def extract_for_freeze(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractionResult:
        """Translate invalid producer input into the typed freeze failure."""
        try:
            return self.extract(source, content)
        except ValueError as error:
            raise FreezableSourceExtractionError(
                "freezable source extraction rejected its input"
            ) from error

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

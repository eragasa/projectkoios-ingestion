from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO

from projectkoios.ingestion.documents import ExtractedTextbook
from projectkoios.ingestion.models import SourceDocument


class TextbookIngester(ABC):
    @abstractmethod
    def ingest(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractedTextbook: ...

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO

from projectkoios.ingestion.documents import ExtractedArticle
from projectkoios.ingestion.models import SourceDocument


class ArticleIngester(ABC):
    @abstractmethod
    def ingest(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractedArticle: ...

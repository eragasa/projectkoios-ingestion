"""Document bases and established extracted-document exports."""

from projectkoios.ingestion.documents.base import (
    AbstractArticle,
    AbstractDocument,
    AbstractTextbook,
)
from projectkoios.ingestion.documents.extracted import (
    ExtractedArticle,
    ExtractedTextbook,
)

__all__ = [
    "AbstractArticle",
    "AbstractDocument",
    "AbstractTextbook",
    "ExtractedArticle",
    "ExtractedTextbook",
]

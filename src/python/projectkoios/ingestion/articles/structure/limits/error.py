"""Article-structure limits error."""

from __future__ import annotations


class ArticleStructureLimitError(ValueError):
    """Raised before article-structure analysis exceeds a configured bound."""

"""Figure-relevance limit failure."""

from __future__ import annotations


class FigureRelevanceLimitError(ValueError):
    """Raised before a relevance contract exceeds a hard bound."""

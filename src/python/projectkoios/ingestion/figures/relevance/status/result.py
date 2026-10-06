"""Figure-relevance selection-result statuses."""

from __future__ import annotations

from enum import StrEnum


class FigureRelevanceStatus(StrEnum):
    """Adapter execution outcome, never relevance acceptance."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"

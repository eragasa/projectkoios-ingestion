"""Question-specific figure-relevance proposal levels."""

from __future__ import annotations

from enum import StrEnum


class FigureRelevanceLevel(StrEnum):
    """Question-specific proposal, never source fact or acceptance."""

    PROPOSED_NECESSARY = "proposed_necessary"
    PROPOSED_SUPPORTING = "proposed_supporting"
    PROPOSED_NOT_NECESSARY = "proposed_not_necessary"

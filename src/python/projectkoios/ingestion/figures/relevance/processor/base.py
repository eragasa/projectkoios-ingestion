"""Nominal figure-relevance processor boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.figures.relevance.identity.processor import (
    FigureRelevanceProcessorIdentity,
)
from projectkoios.ingestion.figures.relevance.request import (
    FigureRelevanceRequest,
)
from projectkoios.ingestion.figures.relevance.result.aggregate import (
    FigureRelevanceResult,
)


class FigureRelevanceProcessor(ABC):
    """Produce question-specific proposals without accepting relevance."""

    __slots__ = ()

    name: str
    version: str

    @abstractmethod
    def identity_for(
        self, request: FigureRelevanceRequest
    ) -> FigureRelevanceProcessorIdentity:
        """Return the exact processor identity for a request."""

    @abstractmethod
    def process(self, request: FigureRelevanceRequest) -> FigureRelevanceResult:
        """Produce relevance proposals for one complete request."""

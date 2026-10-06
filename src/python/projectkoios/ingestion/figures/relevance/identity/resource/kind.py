"""FigureRelevanceResourceIdentityKind figure-relevance definition."""

from __future__ import annotations

from enum import StrEnum


class FigureRelevanceResourceIdentityKind(StrEnum):
    SHA256 = "sha256"
    EXPLICIT = "explicit"

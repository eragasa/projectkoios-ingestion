"""Nominal bases for document representations."""

from __future__ import annotations

from abc import ABC, abstractmethod


class AbstractDocument(ABC):
    """Nominal base shared by identified document representations."""

    __slots__ = ()

    @property
    @abstractmethod
    def document_identity(self) -> str:
        """Return the concrete document representation's stable identity."""


class AbstractArticle(AbstractDocument):
    """Nominal base for article document representations."""

    __slots__ = ()


class AbstractTextbook(AbstractDocument):
    """Nominal base for textbook document representations."""

    __slots__ = ()


__all__ = ["AbstractArticle", "AbstractDocument", "AbstractTextbook"]

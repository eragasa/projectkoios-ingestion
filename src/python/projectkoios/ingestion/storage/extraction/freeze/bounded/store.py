"""Nominal create-once artifact store for bounded extraction results."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ExtractionFreezeStore(ABC):
    """Read or create one exact frozen extraction artifact."""

    @abstractmethod
    def read_if_exists(
        self,
        *,
        artifact_reference: str,
        authority_id: str,
        maximum_bytes: int,
    ) -> bytes | None:
        """Return existing exact bytes, or `None` when no artifact exists."""

    @abstractmethod
    def create_once(
        self,
        *,
        artifact_reference: str,
        authority_id: str,
        content: bytes,
        maximum_bytes: int,
    ) -> bool:
        """Create exact bytes and return true, or verify and return false."""

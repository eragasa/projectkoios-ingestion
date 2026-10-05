"""Nominal reader boundary for exact private extraction artifacts."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ExtractionArtifactReader(ABC):
    """Read one bounded opaque artifact reference under supplied authority."""

    @abstractmethod
    def read(
        self,
        *,
        artifact_reference: str,
        authority_id: str,
        maximum_bytes: int,
    ) -> bytes:
        """Return exact artifact bytes or raise a typed reader error."""

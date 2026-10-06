"""Result of one durable extraction publication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class ExtractionPublicationResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Identity and disk position of one committed publication."""

    CONTRACT_NAME: ClassVar[str] = "extraction-publication-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    document_id: str
    payload_sha256: str
    payload_byte_size: int
    journal_sequence: int
    replayed: bool

    def __post_init__(self) -> None:
        if not self.request_id or not self.document_id:
            raise ValueError("extraction publication result is incomplete")
        if not SHA256Hash.is_canonical(self.payload_sha256):
            raise ValueError("publication payload hash must be SHA-256")
        if self.payload_byte_size <= 0:
            raise ValueError("publication payload size must be positive")
        if self.journal_sequence < 1:
            raise ValueError("journal sequence must be positive")
        if type(self.replayed) is not bool:
            raise TypeError("replayed must be a boolean")

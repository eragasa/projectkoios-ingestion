"""Checksummed disk record for an extraction publication."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.identity import canonical_json


def _record_digest(
    *,
    sequence: int,
    request_id: str,
    document_id: str,
    manifest_id: str,
    payload_sha256: str,
    payload_byte_size: int,
    previous_record_sha256: str | None,
) -> str:
    values = {
        "contract_name": ExtractionPublicationRecord.CONTRACT_NAME,
        "contract_version": ExtractionPublicationRecord.CONTRACT_VERSION,
        "document_id": document_id,
        "manifest_id": manifest_id,
        "payload_byte_size": payload_byte_size,
        "payload_sha256": payload_sha256,
        "previous_record_sha256": previous_record_sha256,
        "request_id": request_id,
        "sequence": sequence,
    }
    return hashlib.sha256(canonical_json(values).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ExtractionPublicationRecord(AbstractImmutableDataObject):
    """One bounded append-only journal record."""

    CONTRACT_NAME: ClassVar[str] = "extraction-publication-record"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    sequence: int
    request_id: str
    document_id: str
    manifest_id: str
    payload_sha256: str
    payload_byte_size: int
    previous_record_sha256: str | None
    record_sha256: str

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        request_id: str,
        document_id: str,
        manifest_id: str,
        payload_sha256: str,
        payload_byte_size: int,
        previous_record_sha256: str | None,
    ) -> ExtractionPublicationRecord:
        return cls(
            sequence=sequence,
            request_id=request_id,
            document_id=document_id,
            manifest_id=manifest_id,
            payload_sha256=payload_sha256,
            payload_byte_size=payload_byte_size,
            previous_record_sha256=previous_record_sha256,
            record_sha256=_record_digest(
                sequence=sequence,
                request_id=request_id,
                document_id=document_id,
                manifest_id=manifest_id,
                payload_sha256=payload_sha256,
                payload_byte_size=payload_byte_size,
                previous_record_sha256=previous_record_sha256,
            ),
        )

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("publication record sequence must be positive")
        if not self.request_id or not self.document_id or not self.manifest_id:
            raise ValueError("publication record is incomplete")
        for value in (self.payload_sha256, self.record_sha256):
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError("publication record hash must be SHA-256")
        if self.previous_record_sha256 is not None and not re.fullmatch(
            r"[0-9a-f]{64}", self.previous_record_sha256
        ):
            raise ValueError("previous publication record hash is invalid")
        if self.payload_byte_size <= 0:
            raise ValueError("publication record payload size must be positive")
        expected = _record_digest(
            sequence=self.sequence,
            request_id=self.request_id,
            document_id=self.document_id,
            manifest_id=self.manifest_id,
            payload_sha256=self.payload_sha256,
            payload_byte_size=self.payload_byte_size,
            previous_record_sha256=self.previous_record_sha256,
        )
        if self.record_sha256 != expected:
            raise ValueError("publication record hash is inconsistent")

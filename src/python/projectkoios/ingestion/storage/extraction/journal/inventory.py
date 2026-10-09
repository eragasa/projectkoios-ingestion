"""Immutable checksummed extraction publication-journal inventory."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.storage.extraction.publication.record import (
    ExtractionPublicationRecord,
)


@dataclass(frozen=True, slots=True, init=False)
class ExtractionPublicationJournalInventory:
    """Retain bounded chain identity without retaining journal records."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_RECORDS: ClassVar[int] = 10_000_000

    inventory_id: str = field(init=False)
    record_count: int = field(init=False)
    head_sha256: str | None = field(init=False)
    records_sha256: str = field(init=False)

    def __init__(self, *records: ExtractionPublicationRecord) -> None:
        values = tuple(records)
        if len(values) > self.MAXIMUM_RECORDS:
            raise ValueError(
                "publication journal record count exceeds its bound"
            )
        digest = hashlib.sha256()
        previous: str | None = None
        for index, record in enumerate(values, start=1):
            if type(record) is not ExtractionPublicationRecord:
                raise TypeError("publication journal record is invalid")
            if record.sequence != index:
                raise ValueError(
                    "publication journal sequence is not canonical"
                )
            if record.previous_record_sha256 != previous:
                raise ValueError("publication journal hash chain is invalid")
            encoded = record.record_sha256.encode("ascii", errors="strict")
            digest.update(len(encoded).to_bytes(8, byteorder="big"))
            digest.update(encoded)
            previous = record.record_sha256
        records_sha256 = digest.hexdigest()
        if not SHA256Hash.is_canonical(records_sha256):
            raise ValueError("publication journal inventory hash is invalid")
        object.__setattr__(self, "record_count", len(values))
        object.__setattr__(self, "head_sha256", previous)
        object.__setattr__(self, "records_sha256", records_sha256)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "extraction-publication-journal-inventory",
                self.CONTRACT_VERSION,
                len(values),
                previous,
                records_sha256,
            ),
        )

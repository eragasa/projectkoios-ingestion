"""Immutable selected-publication inventory from an extraction journal."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.journal.inventory import (
    ExtractionPublicationJournalInventory,
)
from projectkoios.ingestion.storage.extraction.publication.record import (
    ExtractionPublicationRecord,
)


@dataclass(frozen=True, slots=True, init=False)
class ExtractionPublicationSelectionInventory:
    """Bind an exact canonical subset of one validated journal stream."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_RECORDS: ClassVar[int] = 10_000_000

    inventory_id: str = field(init=False)
    source_journal_inventory_id: str = field(init=False)
    publication_count: int = field(init=False)
    first_sequence: int = field(init=False)
    last_sequence: int = field(init=False)
    request_ids_sha256: str = field(init=False)
    record_ids_sha256: str = field(init=False)

    def __init__(
        self,
        *,
        journal_records: tuple[ExtractionPublicationRecord, ...],
        selected_request_ids: tuple[str, ...],
    ) -> None:
        if not isinstance(journal_records, tuple):
            raise TypeError("journal records must be a tuple")
        journal = ExtractionPublicationJournalInventory(*journal_records)
        if (
            not isinstance(selected_request_ids, tuple)
            or not 1 <= len(selected_request_ids) <= self.MAXIMUM_RECORDS
            or any(
                type(value) is not str or not value
                for value in selected_request_ids
            )
        ):
            raise ValueError("selected publication requests are invalid")
        if len(selected_request_ids) != len(set(selected_request_ids)):
            raise ValueError("selected publication requests must be unique")
        selected_ids = set(selected_request_ids)
        records = tuple(
            record
            for record in journal_records
            if record.request_id in selected_ids
        )
        if (
            tuple(record.request_id for record in records)
            != selected_request_ids
        ):
            raise ValueError(
                "selected publication requests do not match the journal"
            )
        request_digest = hashlib.sha256()
        record_digest = hashlib.sha256()
        for record in records:
            for digest, component in (
                (request_digest, record.request_id),
                (record_digest, record.record_sha256),
            ):
                encoded = component.encode("utf-8", errors="strict")
                digest.update(len(encoded).to_bytes(8, byteorder="big"))
                digest.update(encoded)
        request_ids_sha256 = request_digest.hexdigest()
        record_ids_sha256 = record_digest.hexdigest()
        object.__setattr__(
            self, "source_journal_inventory_id", journal.inventory_id
        )
        object.__setattr__(self, "publication_count", len(records))
        object.__setattr__(self, "first_sequence", records[0].sequence)
        object.__setattr__(self, "last_sequence", records[-1].sequence)
        object.__setattr__(self, "request_ids_sha256", request_ids_sha256)
        object.__setattr__(self, "record_ids_sha256", record_ids_sha256)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "extraction-publication-selection-inventory",
                self.CONTRACT_VERSION,
                journal.inventory_id,
                len(records),
                records[0].sequence,
                records[-1].sequence,
                request_ids_sha256,
                record_ids_sha256,
            ),
        )

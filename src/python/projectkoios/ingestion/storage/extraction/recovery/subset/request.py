"""Exact identity-filtered extraction projection recovery request."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.storage.extraction.publication.record import (
    ExtractionPublicationRecord,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionSubsetRecoveryRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Bind one target to an exact journal head and ordered record subset."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"
    AUTHORITY_REQUIREMENT: ClassVar[str] = "extraction_projection_write"
    MAXIMUM_RECORDS: ClassVar[int] = 10_000_000

    request_id: str
    idempotency_key: str
    projection_reference: str
    authority_id: str
    expected_journal_record_count: int
    expected_journal_head_sha256: str | None
    subset_records: tuple[ExtractionPublicationRecord, ...]
    require_empty_projection: bool
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        projection_reference: str,
        authority_id: str,
        expected_journal_record_count: int,
        expected_journal_head_sha256: str | None,
        subset_records: tuple[ExtractionPublicationRecord, ...],
        require_empty_projection: bool,
    ) -> ExtractionProjectionSubsetRecoveryRequest:
        record_ids = tuple(record.record_sha256 for record in subset_records)
        idempotency_key = stable_id(
            "extraction-projection-subset-recovery-idempotency",
            cls.CONTRACT_VERSION,
            projection_reference,
            expected_journal_record_count,
            expected_journal_head_sha256,
            record_ids,
            require_empty_projection,
        )
        return cls(
            request_id=stable_id(
                "extraction-projection-subset-recovery-request",
                cls.CONTRACT_VERSION,
                authority_id,
                idempotency_key,
            ),
            idempotency_key=idempotency_key,
            projection_reference=projection_reference,
            authority_id=authority_id,
            expected_journal_record_count=expected_journal_record_count,
            expected_journal_head_sha256=expected_journal_head_sha256,
            subset_records=subset_records,
            require_empty_projection=require_empty_projection,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported subset-recovery request contract")
        for name, value in (
            ("projection_reference", self.projection_reference),
            ("authority_id", self.authority_id),
        ):
            if type(value) is not str or not value or len(value) > 4_096:
                raise ValueError(f"{name} is invalid")
        if (
            isinstance(self.expected_journal_record_count, bool)
            or not isinstance(self.expected_journal_record_count, int)
            or not 0
            <= self.expected_journal_record_count
            <= self.MAXIMUM_RECORDS
        ):
            raise ValueError("expected journal record count is out of bounds")
        if self.expected_journal_record_count == 0:
            if self.expected_journal_head_sha256 is not None:
                raise ValueError("empty journal cannot have a head")
        elif not SHA256Hash.is_canonical(self.expected_journal_head_sha256):
            raise ValueError("nonempty journal needs a lowercase SHA-256 head")
        if not isinstance(self.subset_records, tuple) or any(
            not isinstance(record, ExtractionPublicationRecord)
            for record in self.subset_records
        ):
            raise TypeError("subset records must be publication records")
        if len(self.subset_records) > self.expected_journal_record_count:
            raise ValueError("subset records exceed the journal count")
        if self.expected_journal_record_count and not self.subset_records:
            raise ValueError("nonempty journal recovery needs subset records")
        sequences = tuple(record.sequence for record in self.subset_records)
        if sequences != tuple(sorted(set(sequences))):
            raise ValueError("subset record sequences are not canonical")
        if any(
            sequence > self.expected_journal_record_count
            for sequence in sequences
        ):
            raise ValueError("subset record sequence exceeds journal count")
        if type(self.require_empty_projection) is not bool:
            raise TypeError("require_empty_projection must be boolean")
        record_ids = tuple(
            record.record_sha256 for record in self.subset_records
        )
        expected_idempotency = stable_id(
            "extraction-projection-subset-recovery-idempotency",
            self.CONTRACT_VERSION,
            self.projection_reference,
            self.expected_journal_record_count,
            self.expected_journal_head_sha256,
            record_ids,
            self.require_empty_projection,
        )
        if self.idempotency_key != expected_idempotency:
            raise ValueError("subset-recovery idempotency is inconsistent")
        expected_request = stable_id(
            "extraction-projection-subset-recovery-request",
            self.CONTRACT_VERSION,
            self.authority_id,
            self.idempotency_key,
        )
        if self.request_id != expected_request:
            raise ValueError("subset-recovery request ID is inconsistent")

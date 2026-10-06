"""Compact backend evidence for one projection subset recovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.storage.extraction.projection.inventory.collection import (  # noqa: E501
    ExtractionProjectionCollectionInventory,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionSubsetRecoveryEvidence(AbstractImmutableDataObject):
    """Observed journal, record outcomes, and resulting projection inventory."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"

    evidence_id: str
    observed_journal_record_count: int
    observed_journal_head_sha256: str | None
    subset_record_count: int
    projected_record_count: int
    unchanged_record_count: int
    last_subset_sequence: int | None
    collections: tuple[ExtractionProjectionCollectionInventory, ...]
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        observed_journal_record_count: int,
        observed_journal_head_sha256: str | None,
        subset_record_count: int,
        projected_record_count: int,
        unchanged_record_count: int,
        last_subset_sequence: int | None,
        collections: tuple[ExtractionProjectionCollectionInventory, ...],
    ) -> ExtractionProjectionSubsetRecoveryEvidence:
        parts = (
            observed_journal_record_count,
            observed_journal_head_sha256,
            subset_record_count,
            projected_record_count,
            unchanged_record_count,
            last_subset_sequence,
            tuple(item.inventory_id for item in collections),
        )
        return cls(
            evidence_id=stable_id(
                "extraction-projection-subset-recovery-evidence",
                cls.CONTRACT_VERSION,
                parts,
            ),
            observed_journal_record_count=observed_journal_record_count,
            observed_journal_head_sha256=observed_journal_head_sha256,
            subset_record_count=subset_record_count,
            projected_record_count=projected_record_count,
            unchanged_record_count=unchanged_record_count,
            last_subset_sequence=last_subset_sequence,
            collections=collections,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported subset-recovery evidence contract")
        counts = (
            self.observed_journal_record_count,
            self.subset_record_count,
            self.projected_record_count,
            self.unchanged_record_count,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in counts
        ):
            raise ValueError("subset-recovery evidence count is invalid")
        if (
            self.projected_record_count + self.unchanged_record_count
            != self.subset_record_count
            or self.subset_record_count > self.observed_journal_record_count
        ):
            raise ValueError("subset-recovery evidence counts conflict")
        if self.observed_journal_record_count == 0:
            if self.observed_journal_head_sha256 is not None:
                raise ValueError("empty observed journal cannot have a head")
        elif not SHA256Hash.is_canonical(self.observed_journal_head_sha256):
            raise ValueError("observed journal head is invalid")
        if self.subset_record_count == 0:
            if self.last_subset_sequence is not None:
                raise ValueError("empty subset cannot have a last sequence")
        elif (
            isinstance(self.last_subset_sequence, bool)
            or not isinstance(self.last_subset_sequence, int)
            or not 1
            <= self.last_subset_sequence
            <= self.observed_journal_record_count
        ):
            raise ValueError("last subset sequence is invalid")
        if not isinstance(self.collections, tuple) or any(
            not isinstance(item, ExtractionProjectionCollectionInventory)
            for item in self.collections
        ):
            raise TypeError("subset-recovery collections are invalid")
        names = tuple(item.collection_name for item in self.collections)
        if names != tuple(sorted(set(names))):
            raise ValueError("subset-recovery collections are not canonical")
        parts = (
            self.observed_journal_record_count,
            self.observed_journal_head_sha256,
            self.subset_record_count,
            self.projected_record_count,
            self.unchanged_record_count,
            self.last_subset_sequence,
            tuple(item.inventory_id for item in self.collections),
        )
        expected = stable_id(
            "extraction-projection-subset-recovery-evidence",
            self.CONTRACT_VERSION,
            parts,
        )
        if self.evidence_id != expected:
            raise ValueError("subset-recovery evidence ID is inconsistent")

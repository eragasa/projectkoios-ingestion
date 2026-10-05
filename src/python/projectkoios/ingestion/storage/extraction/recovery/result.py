"""Result of replaying extraction publications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


@dataclass(frozen=True, slots=True)
class ExtractionProjectionRecoveryResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Bounded projection-recovery counts and position."""

    CONTRACT_NAME: ClassVar[str] = "extraction-projection-recovery-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    observed_records: int
    projected_records: int
    last_journal_sequence: int | None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("recovery result request ID is empty")
        if (
            self.observed_records < 0
            or self.projected_records < 0
            or self.projected_records > self.observed_records
        ):
            raise ValueError("recovery result counts are inconsistent")
        if (self.observed_records == 0) != (
            self.last_journal_sequence is None
        ):
            raise ValueError("recovery result journal position is inconsistent")
        if (
            self.last_journal_sequence is not None
            and self.last_journal_sequence < 1
        ):
            raise ValueError("recovery result journal position is invalid")

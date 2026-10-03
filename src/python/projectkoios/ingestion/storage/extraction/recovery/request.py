"""Request to replay authoritative extraction publications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class ExtractionProjectionRecoveryRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Bounded request to rebuild a projection from disk."""

    CONTRACT_NAME: ClassVar[str] = "extraction-projection-recovery-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAX_RECORDS: ClassVar[int] = 1_000_000

    request_id: str
    maximum_records: int

    @classmethod
    def create(
        cls,
        *,
        maximum_records: int = MAX_RECORDS,
    ) -> ExtractionProjectionRecoveryRequest:
        return cls(
            request_id=stable_id(
                "extraction-projection-recovery-request",
                cls.CONTRACT_VERSION,
                maximum_records,
            ),
            maximum_records=maximum_records,
        )

    def __post_init__(self) -> None:
        if (
            isinstance(self.maximum_records, bool)
            or not isinstance(self.maximum_records, int)
            or not 1 <= self.maximum_records <= self.MAX_RECORDS
        ):
            raise ValueError("recovery record bound is invalid")
        expected = stable_id(
            "extraction-projection-recovery-request",
            self.CONTRACT_VERSION,
            self.maximum_records,
        )
        if self.request_id != expected:
            raise ValueError("recovery request ID is inconsistent")

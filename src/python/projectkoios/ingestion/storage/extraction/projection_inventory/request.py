"""Typed request for a query-only extraction projection inventory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class ExtractionProjectionInventoryRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Identify one projection and the authority used to query it."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"
    AUTHORITY_REQUIREMENT: ClassVar[str] = "extraction_projection_query"
    MAXIMUM_REFERENCE_CHARACTERS: ClassVar[int] = 4_096

    request_id: str
    idempotency_key: str
    projection_reference: str
    authority_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        projection_reference: str,
        authority_id: str,
    ) -> ExtractionProjectionInventoryRequest:
        idempotency_key = stable_id(
            "extraction-projection-inventory-idempotency",
            cls.CONTRACT_VERSION,
            projection_reference,
        )
        return cls(
            request_id=stable_id(
                "extraction-projection-inventory-request",
                cls.CONTRACT_VERSION,
                projection_reference,
                authority_id,
                idempotency_key,
            ),
            idempotency_key=idempotency_key,
            projection_reference=projection_reference,
            authority_id=authority_id,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported projection-inventory request contract"
            )
        for name, value in (
            ("projection_reference", self.projection_reference),
            ("authority_id", self.authority_id),
        ):
            if (
                type(value) is not str
                or not value
                or len(value) > self.MAXIMUM_REFERENCE_CHARACTERS
            ):
                raise ValueError(f"{name} is invalid")
        expected_idempotency = stable_id(
            "extraction-projection-inventory-idempotency",
            self.CONTRACT_VERSION,
            self.projection_reference,
        )
        if self.idempotency_key != expected_idempotency:
            raise ValueError("projection-inventory idempotency is inconsistent")
        expected_request = stable_id(
            "extraction-projection-inventory-request",
            self.CONTRACT_VERSION,
            self.projection_reference,
            self.authority_id,
            self.idempotency_key,
        )
        if self.request_id != expected_request:
            raise ValueError("projection-inventory request ID is inconsistent")

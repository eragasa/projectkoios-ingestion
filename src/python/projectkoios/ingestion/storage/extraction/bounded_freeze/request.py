"""Typed request for one bounded native extraction and create-once freeze."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id

_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class BoundedExtractionFreezeRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Bind exact source/configuration evidence to one freeze target."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"
    SOURCE_AUTHORITY_REQUIREMENT: ClassVar[str] = "private_source_read"
    ARTIFACT_READ_AUTHORITY_REQUIREMENT: ClassVar[str] = (
        "extraction_artifact_read"
    )
    ARTIFACT_WRITE_AUTHORITY_REQUIREMENT: ClassVar[str] = (
        "extraction_artifact_write"
    )
    MAXIMUM_SOURCE_BYTES: ClassVar[int] = 1_000_000_000
    MAXIMUM_ARTIFACT_BYTES: ClassVar[int] = 512_000_000
    MAXIMUM_PAGES: ClassVar[int] = 10_000

    request_id: str
    idempotency_key: str
    source_reference: str
    source_authority_id: str
    artifact_reference: str
    artifact_read_authority_id: str
    artifact_write_authority_id: str
    source_id: str
    media_type: str
    expected_source_sha256: str
    expected_source_byte_size: int
    expected_locator_sha256: str
    expected_page_count: int
    extractor_name: str
    expected_extractor_version: str
    configuration_digest: str
    expected_cache_key: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source_reference: str,
        source_authority_id: str,
        artifact_reference: str,
        artifact_read_authority_id: str,
        artifact_write_authority_id: str,
        source_id: str,
        media_type: str,
        expected_source_sha256: str,
        expected_source_byte_size: int,
        expected_locator_sha256: str,
        expected_page_count: int,
        extractor_name: str,
        expected_extractor_version: str,
        configuration_digest: str,
        expected_cache_key: str,
    ) -> BoundedExtractionFreezeRequest:
        evidence = (
            artifact_reference,
            source_id,
            media_type,
            expected_source_sha256,
            expected_source_byte_size,
            expected_locator_sha256,
            expected_page_count,
            extractor_name,
            expected_extractor_version,
            configuration_digest,
            expected_cache_key,
        )
        idempotency_key = stable_id(
            "bounded-extraction-freeze-idempotency",
            cls.CONTRACT_VERSION,
            evidence,
        )
        return cls(
            request_id=stable_id(
                "bounded-extraction-freeze-request",
                cls.CONTRACT_VERSION,
                source_reference,
                source_authority_id,
                artifact_read_authority_id,
                artifact_write_authority_id,
                idempotency_key,
            ),
            idempotency_key=idempotency_key,
            source_reference=source_reference,
            source_authority_id=source_authority_id,
            artifact_reference=artifact_reference,
            artifact_read_authority_id=artifact_read_authority_id,
            artifact_write_authority_id=artifact_write_authority_id,
            source_id=source_id,
            media_type=media_type,
            expected_source_sha256=expected_source_sha256,
            expected_source_byte_size=expected_source_byte_size,
            expected_locator_sha256=expected_locator_sha256,
            expected_page_count=expected_page_count,
            extractor_name=extractor_name,
            expected_extractor_version=expected_extractor_version,
            configuration_digest=configuration_digest,
            expected_cache_key=expected_cache_key,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported bounded-extraction request contract")
        for name, value in (
            ("source_reference", self.source_reference),
            ("source_authority_id", self.source_authority_id),
            ("artifact_reference", self.artifact_reference),
            ("artifact_read_authority_id", self.artifact_read_authority_id),
            ("artifact_write_authority_id", self.artifact_write_authority_id),
            ("source_id", self.source_id),
            ("extractor_name", self.extractor_name),
            ("expected_extractor_version", self.expected_extractor_version),
            ("configuration_digest", self.configuration_digest),
            ("expected_cache_key", self.expected_cache_key),
        ):
            if type(value) is not str or not value or len(value) > 4_096:
                raise ValueError(f"{name} is invalid")
        if self.media_type != "application/pdf":
            raise ValueError("bounded extraction requires application/pdf")
        for name, value in (
            ("expected_source_sha256", self.expected_source_sha256),
            ("expected_locator_sha256", self.expected_locator_sha256),
        ):
            if type(value) is not str or not _SHA256.fullmatch(value):
                raise ValueError(f"{name} must be lowercase SHA-256")
        if (
            isinstance(self.expected_source_byte_size, bool)
            or not isinstance(self.expected_source_byte_size, int)
            or not 1
            <= self.expected_source_byte_size
            <= self.MAXIMUM_SOURCE_BYTES
        ):
            raise ValueError("expected source byte size is out of bounds")
        if (
            isinstance(self.expected_page_count, bool)
            or not isinstance(self.expected_page_count, int)
            or not 0 <= self.expected_page_count <= self.MAXIMUM_PAGES
        ):
            raise ValueError("expected page count is out of bounds")
        evidence = (
            self.artifact_reference,
            self.source_id,
            self.media_type,
            self.expected_source_sha256,
            self.expected_source_byte_size,
            self.expected_locator_sha256,
            self.expected_page_count,
            self.extractor_name,
            self.expected_extractor_version,
            self.configuration_digest,
            self.expected_cache_key,
        )
        expected_idempotency = stable_id(
            "bounded-extraction-freeze-idempotency",
            self.CONTRACT_VERSION,
            evidence,
        )
        if self.idempotency_key != expected_idempotency:
            raise ValueError("bounded-extraction idempotency is inconsistent")
        expected_request = stable_id(
            "bounded-extraction-freeze-request",
            self.CONTRACT_VERSION,
            self.source_reference,
            self.source_authority_id,
            self.artifact_read_authority_id,
            self.artifact_write_authority_id,
            self.idempotency_key,
        )
        if self.request_id != expected_request:
            raise ValueError("bounded-extraction request ID is inconsistent")

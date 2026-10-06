"""Typed request to validate one retained ExtractionResult artifact."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.sha256.hash import SHA256Hash

_MAX_STRING_CHARACTERS = 4_096


@dataclass(frozen=True, slots=True)
class ExistingExtractionArtifactValidationRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Exact expected evidence for one opaque retained artifact."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"
    AUTHORITY_REQUIREMENT: ClassVar[str] = "private_extraction_artifact_read"
    MAXIMUM_ARTIFACT_BYTES: ClassVar[int] = 512_000_000
    MAXIMUM_PAGES: ClassVar[int] = 100_000
    MAXIMUM_BLOCKS: ClassVar[int] = 10_000_000
    MAXIMUM_WARNINGS: ClassVar[int] = 10_000_000

    request_id: str
    idempotency_key: str
    artifact_reference: str
    authority_id: str
    expected_artifact_sha256: str
    expected_artifact_byte_size: int
    expected_source_sha256: str
    expected_document_id: str
    expected_manifest_id: str
    expected_payload_sha256: str
    expected_payload_byte_size: int
    expected_publication_request_id: str
    expected_page_count: int
    expected_block_count: int
    expected_warning_count: int
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        artifact_reference: str,
        authority_id: str,
        expected_artifact_sha256: str,
        expected_artifact_byte_size: int,
        expected_source_sha256: str,
        expected_document_id: str,
        expected_manifest_id: str,
        expected_payload_sha256: str,
        expected_payload_byte_size: int,
        expected_publication_request_id: str,
        expected_page_count: int,
        expected_block_count: int,
        expected_warning_count: int,
    ) -> ExistingExtractionArtifactValidationRequest:
        evidence = (
            expected_artifact_sha256,
            expected_artifact_byte_size,
            expected_source_sha256,
            expected_document_id,
            expected_manifest_id,
            expected_payload_sha256,
            expected_payload_byte_size,
            expected_publication_request_id,
            expected_page_count,
            expected_block_count,
            expected_warning_count,
        )
        idempotency_key = stable_id(
            "existing-extraction-artifact-validation-idempotency",
            cls.CONTRACT_VERSION,
            evidence,
        )
        return cls(
            request_id=stable_id(
                "existing-extraction-artifact-validation-request",
                cls.CONTRACT_VERSION,
                artifact_reference,
                authority_id,
                idempotency_key,
            ),
            idempotency_key=idempotency_key,
            artifact_reference=artifact_reference,
            authority_id=authority_id,
            expected_artifact_sha256=expected_artifact_sha256,
            expected_artifact_byte_size=expected_artifact_byte_size,
            expected_source_sha256=expected_source_sha256,
            expected_document_id=expected_document_id,
            expected_manifest_id=expected_manifest_id,
            expected_payload_sha256=expected_payload_sha256,
            expected_payload_byte_size=expected_payload_byte_size,
            expected_publication_request_id=expected_publication_request_id,
            expected_page_count=expected_page_count,
            expected_block_count=expected_block_count,
            expected_warning_count=expected_warning_count,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported artifact-validation request contract")
        for name, value in (
            ("artifact_reference", self.artifact_reference),
            ("authority_id", self.authority_id),
            ("expected_document_id", self.expected_document_id),
            ("expected_manifest_id", self.expected_manifest_id),
            (
                "expected_publication_request_id",
                self.expected_publication_request_id,
            ),
        ):
            if (
                type(value) is not str
                or not value
                or len(value) > _MAX_STRING_CHARACTERS
            ):
                raise ValueError(f"{name} is invalid")
        for name, value in (
            ("expected_artifact_sha256", self.expected_artifact_sha256),
            ("expected_source_sha256", self.expected_source_sha256),
            ("expected_payload_sha256", self.expected_payload_sha256),
        ):
            if not SHA256Hash.is_canonical(value):
                raise ValueError(f"{name} must be lowercase SHA-256")
        self._bounded_positive(
            "expected_artifact_byte_size",
            self.expected_artifact_byte_size,
            self.MAXIMUM_ARTIFACT_BYTES,
        )
        self._bounded_positive(
            "expected_payload_byte_size",
            self.expected_payload_byte_size,
            self.MAXIMUM_ARTIFACT_BYTES,
        )
        self._bounded_nonnegative(
            "expected_page_count",
            self.expected_page_count,
            self.MAXIMUM_PAGES,
        )
        self._bounded_nonnegative(
            "expected_block_count",
            self.expected_block_count,
            self.MAXIMUM_BLOCKS,
        )
        self._bounded_nonnegative(
            "expected_warning_count",
            self.expected_warning_count,
            self.MAXIMUM_WARNINGS,
        )
        evidence = (
            self.expected_artifact_sha256,
            self.expected_artifact_byte_size,
            self.expected_source_sha256,
            self.expected_document_id,
            self.expected_manifest_id,
            self.expected_payload_sha256,
            self.expected_payload_byte_size,
            self.expected_publication_request_id,
            self.expected_page_count,
            self.expected_block_count,
            self.expected_warning_count,
        )
        expected_idempotency = stable_id(
            "existing-extraction-artifact-validation-idempotency",
            self.CONTRACT_VERSION,
            evidence,
        )
        if self.idempotency_key != expected_idempotency:
            raise ValueError(
                "artifact-validation idempotency key is inconsistent"
            )
        expected_request = stable_id(
            "existing-extraction-artifact-validation-request",
            self.CONTRACT_VERSION,
            self.artifact_reference,
            self.authority_id,
            self.idempotency_key,
        )
        if self.request_id != expected_request:
            raise ValueError("artifact-validation request ID is inconsistent")

    @staticmethod
    def _bounded_positive(name: str, value: int, maximum: int) -> None:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= maximum
        ):
            raise ValueError(f"{name} is out of bounds")

    @staticmethod
    def _bounded_nonnegative(name: str, value: int, maximum: int) -> None:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= maximum
        ):
            raise ValueError(f"{name} is out of bounds")

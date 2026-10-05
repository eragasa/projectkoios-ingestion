"""Typed request to publish one validated extraction artifact to disk."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.actions.status import (
    ExtractionActionStatus,
)
from projectkoios.ingestion.storage.extraction.artifact_validation.request import (  # noqa: E501
    ExistingExtractionArtifactValidationRequest,
)
from projectkoios.ingestion.storage.extraction.artifact_validation.result import (  # noqa: E501
    ExistingExtractionArtifactValidationResult,
)


@dataclass(frozen=True, slots=True)
class ValidatedExtractionJournalPublicationRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Bind exact validated evidence to one authoritative journal target."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"
    AUTHORITY_REQUIREMENT: ClassVar[str] = "extraction_journal_write"

    request_id: str
    idempotency_key: str
    journal_reference: str
    authority_id: str
    validation_request: ExistingExtractionArtifactValidationRequest
    validation_result: ExistingExtractionArtifactValidationResult
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        journal_reference: str,
        authority_id: str,
        validation_request: ExistingExtractionArtifactValidationRequest,
        validation_result: ExistingExtractionArtifactValidationResult,
    ) -> ValidatedExtractionJournalPublicationRequest:
        idempotency_key = stable_id(
            "validated-extraction-journal-publication-idempotency",
            cls.CONTRACT_VERSION,
            journal_reference,
            validation_request.idempotency_key,
            validation_request.expected_publication_request_id,
        )
        return cls(
            request_id=stable_id(
                "validated-extraction-journal-publication-request",
                cls.CONTRACT_VERSION,
                authority_id,
                validation_request.request_id,
                validation_result.result_id,
                idempotency_key,
            ),
            idempotency_key=idempotency_key,
            journal_reference=journal_reference,
            authority_id=authority_id,
            validation_request=validation_request,
            validation_result=validation_result,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported journal-publication request contract")
        for name, value in (
            ("journal_reference", self.journal_reference),
            ("authority_id", self.authority_id),
        ):
            if type(value) is not str or not value or len(value) > 4_096:
                raise ValueError(f"{name} is invalid")
        if not isinstance(
            self.validation_request,
            ExistingExtractionArtifactValidationRequest,
        ) or not isinstance(
            self.validation_result,
            ExistingExtractionArtifactValidationResult,
        ):
            raise TypeError(
                "journal publication validation evidence is invalid"
            )
        validation = self.validation_result
        expected = self.validation_request
        if (
            validation.request_id != expected.request_id
            or validation.idempotency_key != expected.idempotency_key
            or validation.status is not ExtractionActionStatus.COMPLETED
            or validation.disposition
            is not ExtractionActionDisposition.CONTINUE
            or validation.failure_code is not None
            or validation.artifact_sha256 != expected.expected_artifact_sha256
            or validation.artifact_byte_size
            != expected.expected_artifact_byte_size
            or validation.source_sha256 != expected.expected_source_sha256
            or validation.document_id != expected.expected_document_id
            or validation.manifest_id != expected.expected_manifest_id
            or validation.payload_sha256 != expected.expected_payload_sha256
            or validation.payload_byte_size
            != expected.expected_payload_byte_size
            or validation.publication_request_id
            != expected.expected_publication_request_id
            or validation.page_count != expected.expected_page_count
            or validation.block_count != expected.expected_block_count
            or validation.warning_count != expected.expected_warning_count
        ):
            raise ValueError("journal publication validation evidence differs")
        expected_idempotency = stable_id(
            "validated-extraction-journal-publication-idempotency",
            self.CONTRACT_VERSION,
            self.journal_reference,
            self.validation_request.idempotency_key,
            self.validation_request.expected_publication_request_id,
        )
        if self.idempotency_key != expected_idempotency:
            raise ValueError("journal-publication idempotency is inconsistent")
        expected_request = stable_id(
            "validated-extraction-journal-publication-request",
            self.CONTRACT_VERSION,
            self.authority_id,
            self.validation_request.request_id,
            self.validation_result.result_id,
            self.idempotency_key,
        )
        if self.request_id != expected_request:
            raise ValueError("journal-publication request ID is inconsistent")

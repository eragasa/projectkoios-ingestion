"""Typed result of retained ExtractionResult artifact validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.actions.status import (
    ExtractionActionStatus,
)
from projectkoios.ingestion.storage.extraction.artifact_validation.request import (  # noqa: E501
    ExistingExtractionArtifactValidationRequest,
)


@dataclass(frozen=True, slots=True)
class ExistingExtractionArtifactValidationResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Compact identities and counts, never the validated subject graph."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    request_id: str
    idempotency_key: str
    status: ExtractionActionStatus
    disposition: ExtractionActionDisposition
    failure_code: str | None
    artifact_sha256: str | None
    artifact_byte_size: int | None
    source_sha256: str | None
    document_id: str | None
    manifest_id: str | None
    payload_sha256: str | None
    payload_byte_size: int | None
    publication_request_id: str | None
    page_count: int | None
    block_count: int | None
    warning_count: int | None
    actionizer_name: str
    actionizer_version: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def completed(
        cls,
        *,
        request: ExistingExtractionArtifactValidationRequest,
        actionizer_name: str,
        actionizer_version: str,
    ) -> ExistingExtractionArtifactValidationResult:
        values: tuple[object, ...] = (
            request.expected_artifact_sha256,
            request.expected_artifact_byte_size,
            request.expected_source_sha256,
            request.expected_document_id,
            request.expected_manifest_id,
            request.expected_payload_sha256,
            request.expected_payload_byte_size,
            request.expected_publication_request_id,
            request.expected_page_count,
            request.expected_block_count,
            request.expected_warning_count,
        )
        return cls(
            result_id=cls._result_id(
                request=request,
                status=ExtractionActionStatus.COMPLETED,
                disposition=ExtractionActionDisposition.CONTINUE,
                failure_code=None,
                evidence=values,
                actionizer_name=actionizer_name,
                actionizer_version=actionizer_version,
            ),
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            status=ExtractionActionStatus.COMPLETED,
            disposition=ExtractionActionDisposition.CONTINUE,
            failure_code=None,
            artifact_sha256=request.expected_artifact_sha256,
            artifact_byte_size=request.expected_artifact_byte_size,
            source_sha256=request.expected_source_sha256,
            document_id=request.expected_document_id,
            manifest_id=request.expected_manifest_id,
            payload_sha256=request.expected_payload_sha256,
            payload_byte_size=request.expected_payload_byte_size,
            publication_request_id=request.expected_publication_request_id,
            page_count=request.expected_page_count,
            block_count=request.expected_block_count,
            warning_count=request.expected_warning_count,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    @classmethod
    def failed(
        cls,
        *,
        request: ExistingExtractionArtifactValidationRequest,
        disposition: ExtractionActionDisposition,
        failure_code: str,
        actionizer_name: str,
        actionizer_version: str,
    ) -> ExistingExtractionArtifactValidationResult:
        if disposition is ExtractionActionDisposition.CONTINUE:
            raise ValueError("failed artifact validation cannot continue")
        if not failure_code:
            raise ValueError("failed artifact validation needs a failure code")
        return cls(
            result_id=cls._result_id(
                request=request,
                status=ExtractionActionStatus.FAILED,
                disposition=disposition,
                failure_code=failure_code,
                evidence=(None,) * 11,
                actionizer_name=actionizer_name,
                actionizer_version=actionizer_version,
            ),
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            status=ExtractionActionStatus.FAILED,
            disposition=disposition,
            failure_code=failure_code,
            artifact_sha256=None,
            artifact_byte_size=None,
            source_sha256=None,
            document_id=None,
            manifest_id=None,
            payload_sha256=None,
            payload_byte_size=None,
            publication_request_id=None,
            page_count=None,
            block_count=None,
            warning_count=None,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported artifact-validation result contract")
        if not self.request_id or not self.idempotency_key:
            raise ValueError(
                "artifact-validation result identity is incomplete"
            )
        if not self.actionizer_name or not self.actionizer_version:
            raise ValueError(
                "artifact-validation actionizer identity is incomplete"
            )
        if not isinstance(
            self.status, ExtractionActionStatus
        ) or not isinstance(self.disposition, ExtractionActionDisposition):
            raise TypeError("artifact-validation outcome is invalid")
        if self.failure_code is not None and (
            type(self.failure_code) is not str
            or not self.failure_code
            or len(self.failure_code) > 256
        ):
            raise ValueError("artifact-validation failure code is invalid")
        evidence = self._evidence()
        if self.status is ExtractionActionStatus.COMPLETED:
            if (
                self.disposition is not ExtractionActionDisposition.CONTINUE
                or self.failure_code is not None
                or any(value is None for value in evidence)
            ):
                raise ValueError(
                    "completed artifact-validation result is invalid"
                )
            for hash_value in (
                self.artifact_sha256,
                self.source_sha256,
                self.payload_sha256,
            ):
                if not SHA256Hash.is_canonical(hash_value):
                    raise ValueError("completed result hash is invalid")
            for size_value in (
                self.artifact_byte_size,
                self.payload_byte_size,
            ):
                if (
                    isinstance(size_value, bool)
                    or not isinstance(size_value, int)
                    or size_value <= 0
                ):
                    raise ValueError("completed result byte size is invalid")
            for count_value in (
                self.page_count,
                self.block_count,
                self.warning_count,
            ):
                if (
                    isinstance(count_value, bool)
                    or not isinstance(count_value, int)
                    or count_value < 0
                ):
                    raise ValueError("completed result count is invalid")
            for identity_value in (
                self.document_id,
                self.manifest_id,
                self.publication_request_id,
            ):
                if type(identity_value) is not str or not identity_value:
                    raise ValueError("completed result identity is invalid")
        elif (
            self.status is not ExtractionActionStatus.FAILED
            or self.disposition is ExtractionActionDisposition.CONTINUE
            or not self.failure_code
            or any(value is not None for value in evidence)
        ):
            raise ValueError("failed artifact-validation result is invalid")
        expected = self._result_id(
            request_id=self.request_id,
            idempotency_key=self.idempotency_key,
            status=self.status,
            disposition=self.disposition,
            failure_code=self.failure_code,
            evidence=evidence,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
            contract_version=self.contract_version,
        )
        if self.result_id != expected:
            raise ValueError("artifact-validation result ID is inconsistent")

    def _evidence(self) -> tuple[object, ...]:
        return (
            self.artifact_sha256,
            self.artifact_byte_size,
            self.source_sha256,
            self.document_id,
            self.manifest_id,
            self.payload_sha256,
            self.payload_byte_size,
            self.publication_request_id,
            self.page_count,
            self.block_count,
            self.warning_count,
        )

    @classmethod
    def _result_id(
        cls,
        *,
        status: ExtractionActionStatus,
        disposition: ExtractionActionDisposition,
        failure_code: str | None,
        evidence: tuple[object, ...],
        actionizer_name: str,
        actionizer_version: str,
        request: ExistingExtractionArtifactValidationRequest | None = None,
        request_id: str | None = None,
        idempotency_key: str | None = None,
        contract_version: str | None = None,
    ) -> str:
        actual_request_id = request.request_id if request else request_id
        actual_idempotency = (
            request.idempotency_key if request else idempotency_key
        )
        return stable_id(
            "existing-extraction-artifact-validation-result",
            actual_request_id,
            actual_idempotency,
            status,
            disposition,
            failure_code,
            evidence,
            actionizer_name,
            actionizer_version,
            contract_version or cls.CONTRACT_VERSION,
        )

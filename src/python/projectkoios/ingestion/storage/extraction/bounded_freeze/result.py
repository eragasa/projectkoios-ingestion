"""Typed result for one bounded extraction freeze action."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base import AbstractImmutableDataObject
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
from projectkoios.ingestion.storage.extraction.bounded_freeze.request import (
    BoundedExtractionFreezeRequest,
)


@dataclass(frozen=True, slots=True)
class BoundedExtractionFreezeResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Frozen artifact validation evidence or one typed failure."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    request_id: str
    idempotency_key: str
    status: ExtractionActionStatus
    disposition: ExtractionActionDisposition
    failure_code: str | None
    created: bool | None
    validation_request: ExistingExtractionArtifactValidationRequest | None
    validation_result: ExistingExtractionArtifactValidationResult | None
    actionizer_name: str
    actionizer_version: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def completed(
        cls,
        *,
        request: BoundedExtractionFreezeRequest,
        created: bool,
        validation_request: ExistingExtractionArtifactValidationRequest,
        validation_result: ExistingExtractionArtifactValidationResult,
        actionizer_name: str,
        actionizer_version: str,
    ) -> BoundedExtractionFreezeResult:
        return cls._create(
            request=request,
            status=ExtractionActionStatus.COMPLETED,
            disposition=ExtractionActionDisposition.CONTINUE,
            failure_code=None,
            created=created,
            validation_request=validation_request,
            validation_result=validation_result,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    @classmethod
    def failed(
        cls,
        *,
        request: BoundedExtractionFreezeRequest,
        disposition: ExtractionActionDisposition,
        failure_code: str,
        actionizer_name: str,
        actionizer_version: str,
    ) -> BoundedExtractionFreezeResult:
        if disposition is ExtractionActionDisposition.CONTINUE:
            raise ValueError("failed bounded extraction cannot continue")
        return cls._create(
            request=request,
            status=ExtractionActionStatus.FAILED,
            disposition=disposition,
            failure_code=failure_code,
            created=None,
            validation_request=None,
            validation_result=None,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    @classmethod
    def _create(
        cls,
        *,
        request: BoundedExtractionFreezeRequest,
        status: ExtractionActionStatus,
        disposition: ExtractionActionDisposition,
        failure_code: str | None,
        created: bool | None,
        validation_request: ExistingExtractionArtifactValidationRequest | None,
        validation_result: ExistingExtractionArtifactValidationResult | None,
        actionizer_name: str,
        actionizer_version: str,
    ) -> BoundedExtractionFreezeResult:
        parts = (
            request.request_id,
            request.idempotency_key,
            status,
            disposition,
            failure_code,
            created,
            validation_request.request_id if validation_request else None,
            validation_result.result_id if validation_result else None,
            actionizer_name,
            actionizer_version,
        )
        return cls(
            result_id=stable_id(
                "bounded-extraction-freeze-result",
                cls.CONTRACT_VERSION,
                parts,
            ),
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            status=status,
            disposition=disposition,
            failure_code=failure_code,
            created=created,
            validation_request=validation_request,
            validation_result=validation_result,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported bounded-extraction result contract")
        if not isinstance(
            self.status, ExtractionActionStatus
        ) or not isinstance(self.disposition, ExtractionActionDisposition):
            raise TypeError("bounded-extraction outcome is invalid")
        if not self.request_id or not self.idempotency_key:
            raise ValueError("bounded-extraction result identity is incomplete")
        if not self.actionizer_name or not self.actionizer_version:
            raise ValueError("bounded-extraction actionizer is incomplete")
        if self.status is ExtractionActionStatus.COMPLETED:
            if (
                self.disposition is not ExtractionActionDisposition.CONTINUE
                or self.failure_code is not None
                or type(self.created) is not bool
                or not isinstance(
                    self.validation_request,
                    ExistingExtractionArtifactValidationRequest,
                )
                or not isinstance(
                    self.validation_result,
                    ExistingExtractionArtifactValidationResult,
                )
                or self.validation_result.request_id
                != self.validation_request.request_id
            ):
                raise ValueError(
                    "completed bounded-extraction result is invalid"
                )
        elif (
            self.status is not ExtractionActionStatus.FAILED
            or self.disposition is ExtractionActionDisposition.CONTINUE
            or not self.failure_code
            or self.created is not None
            or self.validation_request is not None
            or self.validation_result is not None
        ):
            raise ValueError("failed bounded-extraction result is invalid")
        parts = (
            self.request_id,
            self.idempotency_key,
            self.status,
            self.disposition,
            self.failure_code,
            self.created,
            self.validation_request.request_id
            if self.validation_request
            else None,
            self.validation_result.result_id
            if self.validation_result
            else None,
            self.actionizer_name,
            self.actionizer_version,
        )
        expected = stable_id(
            "bounded-extraction-freeze-result",
            self.CONTRACT_VERSION,
            parts,
        )
        if self.result_id != expected:
            raise ValueError("bounded-extraction result ID is inconsistent")

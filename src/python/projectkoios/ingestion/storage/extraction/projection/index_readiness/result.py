"""Result of extraction projection index-readiness action."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.actions.status import (
    ExtractionActionStatus,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.evidence import (  # noqa: E501
    ExtractionProjectionIndexReadinessEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.request import (  # noqa: E501
    ExtractionProjectionIndexReadinessRequest,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionIndexReadinessResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Return readiness evidence or one typed provider failure."""

    CONTRACT_NAME: ClassVar[str] = (
        "extraction-projection-index-readiness-result"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    request_id: str
    idempotency_key: str
    target_id: str
    configuration_id: str
    authority_id: str
    status: ExtractionActionStatus
    disposition: ExtractionActionDisposition
    failure_code: str | None
    evidence: ExtractionProjectionIndexReadinessEvidence | None
    actionizer_name: str
    actionizer_version: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def completed(
        cls,
        *,
        request: ExtractionProjectionIndexReadinessRequest,
        evidence: ExtractionProjectionIndexReadinessEvidence,
        actionizer_name: str,
        actionizer_version: str,
    ) -> ExtractionProjectionIndexReadinessResult:
        """Create one completed readiness result."""
        return cls._create(
            request=request,
            status=ExtractionActionStatus.COMPLETED,
            disposition=ExtractionActionDisposition.CONTINUE,
            failure_code=None,
            evidence=evidence,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    @classmethod
    def failed(
        cls,
        *,
        request: ExtractionProjectionIndexReadinessRequest,
        disposition: ExtractionActionDisposition,
        failure_code: str,
        actionizer_name: str,
        actionizer_version: str,
    ) -> ExtractionProjectionIndexReadinessResult:
        """Create one failed readiness result without partial evidence."""
        return cls._create(
            request=request,
            status=ExtractionActionStatus.FAILED,
            disposition=disposition,
            failure_code=failure_code,
            evidence=None,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    @classmethod
    def _create(
        cls,
        *,
        request: ExtractionProjectionIndexReadinessRequest,
        status: ExtractionActionStatus,
        disposition: ExtractionActionDisposition,
        failure_code: str | None,
        evidence: ExtractionProjectionIndexReadinessEvidence | None,
        actionizer_name: str,
        actionizer_version: str,
    ) -> ExtractionProjectionIndexReadinessResult:
        values = (
            request.request_id,
            request.idempotency_key,
            request.target.target_id,
            request.configuration.configuration_id,
            request.authority_id,
            status,
            disposition,
            failure_code,
            evidence.readiness_id if evidence is not None else None,
            actionizer_name,
            actionizer_version,
        )
        return cls(
            result_id=stable_id(
                "extraction-projection-index-readiness-result",
                cls.CONTRACT_VERSION,
                values,
            ),
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            target_id=request.target.target_id,
            configuration_id=request.configuration.configuration_id,
            authority_id=request.authority_id,
            status=status,
            disposition=disposition,
            failure_code=failure_code,
            evidence=evidence,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported index-readiness result")
        if not isinstance(
            self.status, ExtractionActionStatus
        ) or not isinstance(self.disposition, ExtractionActionDisposition):
            raise TypeError("index-readiness outcome is invalid")
        if any(
            type(value) is not str or not value or len(value) > 256
            for value in (self.actionizer_name, self.actionizer_version)
        ):
            raise ValueError("index-readiness actionizer is incomplete")
        if any(
            type(value) is not str or not value
            for value in (
                self.request_id,
                self.idempotency_key,
                self.target_id,
                self.configuration_id,
                self.authority_id,
            )
        ):
            raise ValueError("index-readiness result provenance is incomplete")
        if self.status is ExtractionActionStatus.COMPLETED:
            if (
                self.disposition is not ExtractionActionDisposition.CONTINUE
                or self.failure_code is not None
                or type(self.evidence)
                is not ExtractionProjectionIndexReadinessEvidence
                or self.evidence.target_id != self.target_id
                or self.evidence.configuration_id != self.configuration_id
                or self.evidence.authority_id != self.authority_id
            ):
                raise ValueError("completed index-readiness result is invalid")
        elif (
            self.status is not ExtractionActionStatus.FAILED
            or self.disposition is ExtractionActionDisposition.CONTINUE
            or type(self.failure_code) is not str
            or not self.failure_code
            or len(self.failure_code) > 256
            or self.evidence is not None
        ):
            raise ValueError("failed index-readiness result is invalid")
        values = (
            self.request_id,
            self.idempotency_key,
            self.target_id,
            self.configuration_id,
            self.authority_id,
            self.status,
            self.disposition,
            self.failure_code,
            self.evidence.readiness_id if self.evidence is not None else None,
            self.actionizer_name,
            self.actionizer_version,
        )
        expected = stable_id(
            "extraction-projection-index-readiness-result",
            self.CONTRACT_VERSION,
            values,
        )
        if self.result_id != expected:
            raise ValueError("index-readiness result ID is inconsistent")

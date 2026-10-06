"""Typed result for extraction projection subset recovery."""

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
from projectkoios.ingestion.storage.extraction.recovery.subset.evidence import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryEvidence,
)
from projectkoios.ingestion.storage.extraction.recovery.subset.request import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryRequest,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionSubsetRecoveryResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Successful compact evidence or one typed recovery failure."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    request_id: str
    idempotency_key: str
    projection_reference: str
    status: ExtractionActionStatus
    disposition: ExtractionActionDisposition
    failure_code: str | None
    evidence: ExtractionProjectionSubsetRecoveryEvidence | None
    actionizer_name: str
    actionizer_version: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def completed(
        cls,
        *,
        request: ExtractionProjectionSubsetRecoveryRequest,
        evidence: ExtractionProjectionSubsetRecoveryEvidence,
        actionizer_name: str,
        actionizer_version: str,
    ) -> ExtractionProjectionSubsetRecoveryResult:
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
        request: ExtractionProjectionSubsetRecoveryRequest,
        disposition: ExtractionActionDisposition,
        failure_code: str,
        actionizer_name: str,
        actionizer_version: str,
    ) -> ExtractionProjectionSubsetRecoveryResult:
        if disposition is ExtractionActionDisposition.CONTINUE:
            raise ValueError("failed subset recovery cannot continue")
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
        request: ExtractionProjectionSubsetRecoveryRequest,
        status: ExtractionActionStatus,
        disposition: ExtractionActionDisposition,
        failure_code: str | None,
        evidence: ExtractionProjectionSubsetRecoveryEvidence | None,
        actionizer_name: str,
        actionizer_version: str,
    ) -> ExtractionProjectionSubsetRecoveryResult:
        parts = (
            request.request_id,
            request.idempotency_key,
            request.projection_reference,
            status,
            disposition,
            failure_code,
            evidence.evidence_id if evidence else None,
            actionizer_name,
            actionizer_version,
        )
        return cls(
            result_id=stable_id(
                "extraction-projection-subset-recovery-result",
                cls.CONTRACT_VERSION,
                parts,
            ),
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            projection_reference=request.projection_reference,
            status=status,
            disposition=disposition,
            failure_code=failure_code,
            evidence=evidence,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported subset-recovery result contract")
        if not isinstance(
            self.status, ExtractionActionStatus
        ) or not isinstance(self.disposition, ExtractionActionDisposition):
            raise TypeError("subset-recovery outcome is invalid")
        for value in (
            self.request_id,
            self.idempotency_key,
            self.projection_reference,
            self.actionizer_name,
            self.actionizer_version,
        ):
            if type(value) is not str or not value:
                raise ValueError(
                    "subset-recovery result identity is incomplete"
                )
        if self.failure_code is not None and (
            type(self.failure_code) is not str
            or not self.failure_code
            or len(self.failure_code) > 256
        ):
            raise ValueError("subset-recovery failure code is invalid")
        if self.status is ExtractionActionStatus.COMPLETED:
            if (
                self.disposition is not ExtractionActionDisposition.CONTINUE
                or self.failure_code is not None
                or not isinstance(
                    self.evidence,
                    ExtractionProjectionSubsetRecoveryEvidence,
                )
            ):
                raise ValueError("completed subset-recovery result is invalid")
        elif (
            self.status is not ExtractionActionStatus.FAILED
            or self.disposition is ExtractionActionDisposition.CONTINUE
            or not self.failure_code
            or self.evidence is not None
        ):
            raise ValueError("failed subset-recovery result is invalid")
        parts = (
            self.request_id,
            self.idempotency_key,
            self.projection_reference,
            self.status,
            self.disposition,
            self.failure_code,
            self.evidence.evidence_id if self.evidence else None,
            self.actionizer_name,
            self.actionizer_version,
        )
        expected = stable_id(
            "extraction-projection-subset-recovery-result",
            self.CONTRACT_VERSION,
            parts,
        )
        if self.result_id != expected:
            raise ValueError("subset-recovery result ID is inconsistent")

"""Typed result for selected extraction projection recovery."""

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
from projectkoios.ingestion.storage.extraction.selected_recovery.evidence import (  # noqa: E501
    SelectedExtractionProjectionRecoveryEvidence,
)
from projectkoios.ingestion.storage.extraction.selected_recovery.request import (  # noqa: E501
    SelectedExtractionProjectionRecoveryRequest,
)


@dataclass(frozen=True, slots=True)
class SelectedExtractionProjectionRecoveryResult(
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
    evidence: SelectedExtractionProjectionRecoveryEvidence | None
    actionizer_name: str
    actionizer_version: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def completed(
        cls,
        *,
        request: SelectedExtractionProjectionRecoveryRequest,
        evidence: SelectedExtractionProjectionRecoveryEvidence,
        actionizer_name: str,
        actionizer_version: str,
    ) -> SelectedExtractionProjectionRecoveryResult:
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
        request: SelectedExtractionProjectionRecoveryRequest,
        disposition: ExtractionActionDisposition,
        failure_code: str,
        actionizer_name: str,
        actionizer_version: str,
    ) -> SelectedExtractionProjectionRecoveryResult:
        if disposition is ExtractionActionDisposition.CONTINUE:
            raise ValueError("failed selected recovery cannot continue")
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
        request: SelectedExtractionProjectionRecoveryRequest,
        status: ExtractionActionStatus,
        disposition: ExtractionActionDisposition,
        failure_code: str | None,
        evidence: SelectedExtractionProjectionRecoveryEvidence | None,
        actionizer_name: str,
        actionizer_version: str,
    ) -> SelectedExtractionProjectionRecoveryResult:
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
                "selected-extraction-projection-recovery-result",
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
            raise ValueError("unsupported selected-recovery result contract")
        if not isinstance(
            self.status, ExtractionActionStatus
        ) or not isinstance(self.disposition, ExtractionActionDisposition):
            raise TypeError("selected-recovery outcome is invalid")
        for value in (
            self.request_id,
            self.idempotency_key,
            self.projection_reference,
            self.actionizer_name,
            self.actionizer_version,
        ):
            if type(value) is not str or not value:
                raise ValueError(
                    "selected-recovery result identity is incomplete"
                )
        if self.failure_code is not None and (
            type(self.failure_code) is not str
            or not self.failure_code
            or len(self.failure_code) > 256
        ):
            raise ValueError("selected-recovery failure code is invalid")
        if self.status is ExtractionActionStatus.COMPLETED:
            if (
                self.disposition is not ExtractionActionDisposition.CONTINUE
                or self.failure_code is not None
                or not isinstance(
                    self.evidence,
                    SelectedExtractionProjectionRecoveryEvidence,
                )
            ):
                raise ValueError(
                    "completed selected-recovery result is invalid"
                )
        elif (
            self.status is not ExtractionActionStatus.FAILED
            or self.disposition is ExtractionActionDisposition.CONTINUE
            or not self.failure_code
            or self.evidence is not None
        ):
            raise ValueError("failed selected-recovery result is invalid")
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
            "selected-extraction-projection-recovery-result",
            self.CONTRACT_VERSION,
            parts,
        )
        if self.result_id != expected:
            raise ValueError("selected-recovery result ID is inconsistent")

"""Typed result of one validated extraction journal publication."""

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
from projectkoios.ingestion.storage.extraction.journal_publication.request import (  # noqa: E501
    ValidatedExtractionJournalPublicationRequest,
)
from projectkoios.ingestion.storage.extraction.publication.record import (
    ExtractionPublicationRecord,
)
from projectkoios.ingestion.storage.extraction.publication.result import (
    ExtractionPublicationResult,
)


@dataclass(frozen=True, slots=True)
class ValidatedExtractionJournalPublicationResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """One exact publication record or a typed terminal/retry outcome."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    request_id: str
    idempotency_key: str
    journal_reference: str
    status: ExtractionActionStatus
    disposition: ExtractionActionDisposition
    failure_code: str | None
    publication: ExtractionPublicationResult | None
    record: ExtractionPublicationRecord | None
    actionizer_name: str
    actionizer_version: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def completed(
        cls,
        *,
        request: ValidatedExtractionJournalPublicationRequest,
        publication: ExtractionPublicationResult,
        record: ExtractionPublicationRecord,
        actionizer_name: str,
        actionizer_version: str,
    ) -> ValidatedExtractionJournalPublicationResult:
        return cls._create(
            request=request,
            status=ExtractionActionStatus.COMPLETED,
            disposition=ExtractionActionDisposition.CONTINUE,
            failure_code=None,
            publication=publication,
            record=record,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    @classmethod
    def failed(
        cls,
        *,
        request: ValidatedExtractionJournalPublicationRequest,
        disposition: ExtractionActionDisposition,
        failure_code: str,
        actionizer_name: str,
        actionizer_version: str,
    ) -> ValidatedExtractionJournalPublicationResult:
        if disposition is ExtractionActionDisposition.CONTINUE:
            raise ValueError("failed journal publication cannot continue")
        return cls._create(
            request=request,
            status=ExtractionActionStatus.FAILED,
            disposition=disposition,
            failure_code=failure_code,
            publication=None,
            record=None,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    @classmethod
    def _create(
        cls,
        *,
        request: ValidatedExtractionJournalPublicationRequest,
        status: ExtractionActionStatus,
        disposition: ExtractionActionDisposition,
        failure_code: str | None,
        publication: ExtractionPublicationResult | None,
        record: ExtractionPublicationRecord | None,
        actionizer_name: str,
        actionizer_version: str,
    ) -> ValidatedExtractionJournalPublicationResult:
        parts = (
            request.request_id,
            request.idempotency_key,
            request.journal_reference,
            status,
            disposition,
            failure_code,
            record.record_sha256 if record else None,
            publication.replayed if publication else None,
            actionizer_name,
            actionizer_version,
        )
        return cls(
            result_id=stable_id(
                "validated-extraction-journal-publication-result",
                cls.CONTRACT_VERSION,
                parts,
            ),
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            journal_reference=request.journal_reference,
            status=status,
            disposition=disposition,
            failure_code=failure_code,
            publication=publication,
            record=record,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported journal-publication result contract")
        if not isinstance(
            self.status, ExtractionActionStatus
        ) or not isinstance(self.disposition, ExtractionActionDisposition):
            raise TypeError("journal-publication outcome is invalid")
        for value in (
            self.request_id,
            self.idempotency_key,
            self.journal_reference,
            self.actionizer_name,
            self.actionizer_version,
        ):
            if type(value) is not str or not value:
                raise ValueError("journal-publication identity is incomplete")
        if self.failure_code is not None and (
            type(self.failure_code) is not str
            or not self.failure_code
            or len(self.failure_code) > 256
        ):
            raise ValueError("journal-publication failure code is invalid")
        if self.status is ExtractionActionStatus.COMPLETED:
            if (
                self.disposition is not ExtractionActionDisposition.CONTINUE
                or self.failure_code is not None
                or not isinstance(self.publication, ExtractionPublicationResult)
                or not isinstance(self.record, ExtractionPublicationRecord)
            ):
                raise ValueError("completed journal publication is invalid")
            if (
                self.publication.request_id != self.record.request_id
                or self.publication.document_id != self.record.document_id
                or self.publication.payload_sha256 != self.record.payload_sha256
                or self.publication.payload_byte_size
                != self.record.payload_byte_size
                or self.publication.journal_sequence != self.record.sequence
            ):
                raise ValueError("journal publication evidence conflicts")
        elif (
            self.status is not ExtractionActionStatus.FAILED
            or self.disposition is ExtractionActionDisposition.CONTINUE
            or not self.failure_code
            or self.publication is not None
            or self.record is not None
        ):
            raise ValueError("failed journal-publication result is invalid")
        parts = (
            self.request_id,
            self.idempotency_key,
            self.journal_reference,
            self.status,
            self.disposition,
            self.failure_code,
            self.record.record_sha256 if self.record else None,
            self.publication.replayed if self.publication else None,
            self.actionizer_name,
            self.actionizer_version,
        )
        expected = stable_id(
            "validated-extraction-journal-publication-result",
            self.CONTRACT_VERSION,
            parts,
        )
        if self.result_id != expected:
            raise ValueError("journal-publication result ID is inconsistent")

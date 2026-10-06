"""Typed actionizer for exact extraction projection subset recovery."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.recovery.subset.backend.base import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryBackend,
)
from projectkoios.ingestion.storage.extraction.recovery.subset.backend.error import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryBackendError,
)
from projectkoios.ingestion.storage.extraction.recovery.subset.request import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryRequest,
)
from projectkoios.ingestion.storage.extraction.recovery.subset.result import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryResult,
)


class ExtractionProjectionSubsetRecoveryActionizer(
    DataObjectActionizer[
        ExtractionProjectionSubsetRecoveryRequest,
        ExtractionProjectionSubsetRecoveryResult,
    ]
):
    """Recover all and only the records bound by one immutable request."""

    __slots__ = ("backend",)

    actionizer_name = "extraction-projection-subset-recovery"
    actionizer_version = "1"
    collection_names = (
        "extraction_blocks",
        "extraction_documents",
        "extraction_manifests",
        "extraction_pages",
        "extraction_warnings",
    )

    def __init__(
        self,
        *,
        backend: ExtractionProjectionSubsetRecoveryBackend,
    ) -> None:
        if not isinstance(backend, ExtractionProjectionSubsetRecoveryBackend):
            raise TypeError(
                "backend must be an ExtractionProjectionSubsetRecoveryBackend"
            )
        self.backend = backend

    def action(
        self,
        *,
        request: ExtractionProjectionSubsetRecoveryRequest,
    ) -> ExtractionProjectionSubsetRecoveryResult:
        if not isinstance(request, ExtractionProjectionSubsetRecoveryRequest):
            raise TypeError(
                "request must be an ExtractionProjectionSubsetRecoveryRequest"
            )
        try:
            evidence = self.backend.recover_subset(request=request)
        except ExtractionProjectionSubsetRecoveryBackendError as error:
            return ExtractionProjectionSubsetRecoveryResult.failed(
                request=request,
                disposition=error.disposition,
                failure_code=error.code,
                actionizer_name=self.actionizer_name,
                actionizer_version=self.actionizer_version,
            )
        expected_last = (
            request.subset_records[-1].sequence
            if request.subset_records
            else None
        )
        names = tuple(item.collection_name for item in evidence.collections)
        if (
            evidence.observed_journal_record_count
            != request.expected_journal_record_count
            or evidence.observed_journal_head_sha256
            != request.expected_journal_head_sha256
            or evidence.subset_record_count != len(request.subset_records)
            or evidence.last_subset_sequence != expected_last
            or names != self.collection_names
        ):
            return ExtractionProjectionSubsetRecoveryResult.failed(
                request=request,
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                failure_code="subset_recovery_evidence_differs",
                actionizer_name=self.actionizer_name,
                actionizer_version=self.actionizer_version,
            )
        return ExtractionProjectionSubsetRecoveryResult.completed(
            request=request,
            evidence=evidence,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )

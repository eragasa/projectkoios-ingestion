"""Typed actionizer for exact selected extraction projection recovery."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.selected_recovery.backend import (  # noqa: E501
    SelectedExtractionProjectionRecoveryBackend,
)
from projectkoios.ingestion.storage.extraction.selected_recovery.backend_error import (  # noqa: E501
    SelectedExtractionProjectionRecoveryBackendError,
)
from projectkoios.ingestion.storage.extraction.selected_recovery.request import (  # noqa: E501
    SelectedExtractionProjectionRecoveryRequest,
)
from projectkoios.ingestion.storage.extraction.selected_recovery.result import (  # noqa: E501
    SelectedExtractionProjectionRecoveryResult,
)


class SelectedExtractionProjectionRecoveryActionizer(
    DataObjectActionizer[
        SelectedExtractionProjectionRecoveryRequest,
        SelectedExtractionProjectionRecoveryResult,
    ]
):
    """Recover all and only the records bound by one immutable request."""

    __slots__ = ("backend",)

    actionizer_name = "selected-extraction-projection-recovery"
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
        backend: SelectedExtractionProjectionRecoveryBackend,
    ) -> None:
        if not isinstance(backend, SelectedExtractionProjectionRecoveryBackend):
            raise TypeError(
                "backend must be a SelectedExtractionProjectionRecoveryBackend"
            )
        self.backend = backend

    def action(
        self,
        *,
        request: SelectedExtractionProjectionRecoveryRequest,
    ) -> SelectedExtractionProjectionRecoveryResult:
        if not isinstance(request, SelectedExtractionProjectionRecoveryRequest):
            raise TypeError(
                "request must be a SelectedExtractionProjectionRecoveryRequest"
            )
        try:
            evidence = self.backend.recover_selected(request=request)
        except SelectedExtractionProjectionRecoveryBackendError as error:
            return SelectedExtractionProjectionRecoveryResult.failed(
                request=request,
                disposition=error.disposition,
                failure_code=error.code,
                actionizer_name=self.actionizer_name,
                actionizer_version=self.actionizer_version,
            )
        expected_last = (
            request.selected_records[-1].sequence
            if request.selected_records
            else None
        )
        names = tuple(item.collection_name for item in evidence.collections)
        if (
            evidence.observed_journal_record_count
            != request.expected_journal_record_count
            or evidence.observed_journal_head_sha256
            != request.expected_journal_head_sha256
            or evidence.selected_record_count != len(request.selected_records)
            or evidence.last_selected_sequence != expected_last
            or names != self.collection_names
        ):
            return SelectedExtractionProjectionRecoveryResult.failed(
                request=request,
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                failure_code="selected_recovery_evidence_differs",
                actionizer_name=self.actionizer_name,
                actionizer_version=self.actionizer_version,
            )
        return SelectedExtractionProjectionRecoveryResult.completed(
            request=request,
            evidence=evidence,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )

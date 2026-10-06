"""Input-warning derivation for reconciliation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectkoios.ingestion.models import (
    WarningSeverity,
)
from projectkoios.ingestion.ocr.status.selection import OCRSelectionStatus

if TYPE_CHECKING:
    from projectkoios.ingestion.reconciliation.request import (
        OCRReconciliationRequest,
    )
    from projectkoios.ingestion.reconciliation.warning import (
        OCRReconciliationWarning,
    )


def _input_warnings(
    reconciliation_input: OCRReconciliationRequest,
) -> list[OCRReconciliationWarning]:
    from projectkoios.ingestion.reconciliation.warning import (
        OCRReconciliationWarning,
    )

    warnings: list[OCRReconciliationWarning] = []
    selection_result = reconciliation_input.selection_result
    if selection_result.status is not OCRSelectionStatus.COMPLETED:
        warnings.append(
            OCRReconciliationWarning.create(
                code="ocr.reconciliation.incomplete_ocr_stream",
                severity=WarningSeverity.WARNING,
                message=(
                    "OCR stream is partial or failed; reconciliation "
                    "is incomplete"
                ),
                object_ids=(selection_result.selection_result_id,),
                evidence=(("status", selection_result.status.value),),
            )
        )
    layout = reconciliation_input.layout_result
    if layout is not None and layout.warnings:
        warnings.append(
            OCRReconciliationWarning.create(
                code="ocr.reconciliation.uncertain_native_order",
                severity=WarningSeverity.WARNING,
                message=("Native reading order retains layout uncertainty"),
                object_ids=(layout.result_id,),
                evidence=(("layout_warning_count", str(len(layout.warnings))),),
            )
        )
    return warnings

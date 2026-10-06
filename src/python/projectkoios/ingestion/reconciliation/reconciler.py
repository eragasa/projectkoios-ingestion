"""DeterministicOCRReconciler reconciliation domain object."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.models import WarningSeverity
from projectkoios.ingestion.reconciliation.base import OCRReconciler
from projectkoios.ingestion.reconciliation.derivation import (
    match as match_derivation,
)
from projectkoios.ingestion.reconciliation.derivation import (
    native as native_derivation,
)
from projectkoios.ingestion.reconciliation.derivation import (
    stream as stream_derivation,
)
from projectkoios.ingestion.reconciliation.derivation import (
    warning as warning_derivation,
)
from projectkoios.ingestion.reconciliation.limit.error import (
    OCRReconciliationLimitError,
)
from projectkoios.ingestion.reconciliation.request import (
    OCRReconciliationRequest,
)
from projectkoios.ingestion.reconciliation.result import OCRReconciliationResult
from projectkoios.ingestion.reconciliation.warning import (
    OCRReconciliationWarning,
)


class DeterministicOCRReconciler(
    DataObjectActionizer[OCRReconciliationRequest, OCRReconciliationResult],
    OCRReconciler,
):
    """Conservatively propose a merged stream without replacing evidence."""

    __slots__ = ()

    name = "deterministic-ocr-reconciler"
    version = "1"

    def action(
        self, *, request: OCRReconciliationRequest
    ) -> OCRReconciliationResult:
        """Return the reconciliation result for one complete request."""
        if not isinstance(request, OCRReconciliationRequest):
            raise TypeError("request must be OCRReconciliationRequest")
        return self._reconcile(request)

    def reconcile(
        self, reconciliation_input: OCRReconciliationRequest
    ) -> OCRReconciliationResult:
        """Reconcile one complete native/OCR evidence request."""
        return self.action(request=reconciliation_input)

    def _reconcile(
        self, reconciliation_input: OCRReconciliationRequest
    ) -> OCRReconciliationResult:
        native_stream = native_derivation._native_stream(reconciliation_input)
        native_segments = native_derivation._native_segments(
            native_stream, reconciliation_input.configuration
        )
        ocr_stream = reconciliation_input.selection_result.lines
        config = reconciliation_input.configuration
        if len(ocr_stream) > config.max_ocr_lines:
            raise OCRReconciliationLimitError(
                "OCR line count exceeds max_ocr_lines"
            )
        if reconciliation_input.selection_result.tokens and not ocr_stream:
            raise ValueError(
                "OCR reconciliation requires line evidence, not tokens alone"
            )
        pair_count = len(native_segments) * len(ocr_stream)
        if pair_count > config.max_candidate_pairs:
            raise OCRReconciliationLimitError(
                "candidate pairs exceed max_candidate_pairs"
            )
        warnings = warning_derivation._input_warnings(reconciliation_input)
        candidates, comparison_warnings = match_derivation._candidates(
            native_segments, ocr_stream, config
        )
        warnings.extend(comparison_warnings)
        selected_candidates, match_warnings = match_derivation._matches(
            candidates, config
        )
        warnings.extend(match_warnings)
        matched_ocr_ids = {
            candidate.ocr_line_id for candidate in selected_candidates
        }
        unmatched_ocr_ids = tuple(
            line.line_id
            for line in ocr_stream
            if line.line_id not in matched_ocr_ids
        )
        if native_segments and unmatched_ocr_ids:
            warnings.append(
                OCRReconciliationWarning.create(
                    code="ocr.reconciliation.ocr_only_order_uncertain",
                    severity=WarningSeverity.WARNING,
                    message=(
                        "Unmatched OCR evidence is appended after the "
                        "layout-ordered native stream"
                    ),
                    object_ids=unmatched_ocr_ids,
                    evidence=(("ordering_policy", "append_after_native"),),
                )
            )
        if len(warnings) > config.max_warnings:
            raise OCRReconciliationLimitError(
                "warning count exceeds max_warnings"
            )
        warning_by_id = {warning.warning_id: warning for warning in warnings}
        matches = tuple(
            match_derivation._match_with_warning(candidate, warning_by_id)
            for candidate in selected_candidates
        )
        proposed = stream_derivation._merged_stream(
            native_segments,
            ocr_stream,
            matches,
            tuple(warnings),
        )
        return OCRReconciliationResult.create(
            reconciliation_input=reconciliation_input,
            native_stream=native_stream,
            native_segments=native_segments,
            ocr_stream=ocr_stream,
            matches=matches,
            proposed_merged_stream=proposed,
            warnings=tuple(warnings),
            processor_name=self.name,
            processor_version=self.version,
        )

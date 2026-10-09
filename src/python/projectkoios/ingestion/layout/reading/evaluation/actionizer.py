"""Pure deterministic reading-order replica evaluator."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer

from .derivation import derive_layout_reading_order_evaluation
from .request import LayoutReadingOrderEvaluationRequest
from .result import LayoutReadingOrderEvaluationResult


class LayoutReadingOrderEvaluationActionizer(
    DataObjectActionizer[
        LayoutReadingOrderEvaluationRequest,
        LayoutReadingOrderEvaluationResult,
    ]
):
    """Aggregate already-normalized judgments without external side effects."""

    def action(
        self, *, request: LayoutReadingOrderEvaluationRequest
    ) -> LayoutReadingOrderEvaluationResult:
        """Evaluate one candidate against one complete declared replica set."""
        if type(request) is not LayoutReadingOrderEvaluationRequest:
            raise TypeError(
                "request must be LayoutReadingOrderEvaluationRequest"
            )
        (
            agreement,
            coverage,
            considered,
            valid,
            alignments,
            disagreements,
            missing,
            malformed,
            reasons,
        ) = derive_layout_reading_order_evaluation(request=request)
        return LayoutReadingOrderEvaluationResult(
            request=request,
            replica_agreement=agreement,
            aggregate_coverage=coverage,
            considered_evidence_ids=considered,
            valid_evidence_ids=valid,
            candidate_alignments=alignments,
            disagreement_pairs=disagreements,
            missing_evidence=missing,
            malformed_evidence=malformed,
            escalation_reasons=reasons,
            escalation_required=len(reasons) != 0,
        )

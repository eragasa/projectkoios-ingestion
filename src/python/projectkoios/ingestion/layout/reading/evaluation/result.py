"""Immutable result of deterministic reading-order replica evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.identity import stable_id

from .alignment import LayoutReadingOrderReplicaAlignmentInventory
from .derivation import derive_layout_reading_order_evaluation
from .disagreement import LayoutReadingOrderReplicaDisagreementPairInventory
from .identity import LayoutReadingOrderReplicaEvidenceIdentityInventory
from .malformed import LayoutReadingOrderMalformedReplicaEvidenceInventory
from .missing import LayoutReadingOrderMissingReplicaEvidenceInventory
from .reason import LayoutReadingOrderEvaluationEscalationReasonInventory
from .request import LayoutReadingOrderEvaluationRequest
from .status import (
    LayoutReadingOrderAggregateCoverage,
    LayoutReadingOrderReplicaAgreement,
)


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderEvaluationResult(DataObjectActionResult):
    """Report evidence quality without choosing or finalizing an order."""

    CONTRACT_NAME: ClassVar[str] = "layout-reading-order-evaluation-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    ACTIONIZER_NAME: ClassVar[str] = "layout-reading-order-evaluator"
    ACTIONIZER_VERSION: ClassVar[str] = "1.0"

    request: LayoutReadingOrderEvaluationRequest
    replica_agreement: LayoutReadingOrderReplicaAgreement
    aggregate_coverage: LayoutReadingOrderAggregateCoverage
    considered_evidence_ids: LayoutReadingOrderReplicaEvidenceIdentityInventory
    valid_evidence_ids: LayoutReadingOrderReplicaEvidenceIdentityInventory
    candidate_alignments: LayoutReadingOrderReplicaAlignmentInventory
    disagreement_pairs: LayoutReadingOrderReplicaDisagreementPairInventory
    missing_evidence: LayoutReadingOrderMissingReplicaEvidenceInventory
    malformed_evidence: LayoutReadingOrderMalformedReplicaEvidenceInventory
    escalation_reasons: LayoutReadingOrderEvaluationEscalationReasonInventory
    escalation_required: bool
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not LayoutReadingOrderEvaluationRequest:
            raise TypeError(
                "request must be LayoutReadingOrderEvaluationRequest"
            )
        if not isinstance(
            self.replica_agreement, LayoutReadingOrderReplicaAgreement
        ):
            raise TypeError("replica_agreement uses an invalid enum")
        if not isinstance(
            self.aggregate_coverage, LayoutReadingOrderAggregateCoverage
        ):
            raise TypeError("aggregate_coverage uses an invalid enum")
        if (
            type(self.considered_evidence_ids)
            is not LayoutReadingOrderReplicaEvidenceIdentityInventory
        ):
            raise TypeError(
                "considered_evidence_ids must be an identity inventory"
            )
        if (
            type(self.valid_evidence_ids)
            is not LayoutReadingOrderReplicaEvidenceIdentityInventory
        ):
            raise TypeError("valid_evidence_ids must be an identity inventory")
        if (
            type(self.candidate_alignments)
            is not LayoutReadingOrderReplicaAlignmentInventory
        ):
            raise TypeError(
                "candidate_alignments must be an alignment inventory"
            )
        if (
            type(self.disagreement_pairs)
            is not LayoutReadingOrderReplicaDisagreementPairInventory
        ):
            raise TypeError(
                "disagreement_pairs must be a disagreement inventory"
            )
        if (
            type(self.missing_evidence)
            is not LayoutReadingOrderMissingReplicaEvidenceInventory
        ):
            raise TypeError(
                "missing_evidence must be a missing evidence inventory"
            )
        if (
            type(self.malformed_evidence)
            is not LayoutReadingOrderMalformedReplicaEvidenceInventory
        ):
            raise TypeError(
                "malformed_evidence must be a malformed evidence inventory"
            )
        if (
            type(self.escalation_reasons)
            is not LayoutReadingOrderEvaluationEscalationReasonInventory
        ):
            raise TypeError(
                "escalation_reasons must be an escalation reason inventory"
            )
        if not isinstance(self.escalation_required, bool):
            raise TypeError("escalation_required must be a boolean")
        derived = derive_layout_reading_order_evaluation(request=self.request)
        supplied = (
            self.replica_agreement,
            self.aggregate_coverage,
            self.considered_evidence_ids,
            self.valid_evidence_ids,
            self.candidate_alignments,
            self.disagreement_pairs,
            self.missing_evidence,
            self.malformed_evidence,
            self.escalation_reasons,
        )
        if supplied != derived:
            raise ValueError(
                "reading-order evaluation result differs from derivation"
            )
        if self.escalation_required != (len(self.escalation_reasons) != 0):
            raise ValueError(
                "escalation flag differs from deterministic reasons"
            )
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.request.request_id,
                self.replica_agreement,
                self.aggregate_coverage,
                self.considered_evidence_ids.inventory_id,
                self.valid_evidence_ids.inventory_id,
                self.candidate_alignments.inventory_id,
                self.disagreement_pairs.inventory_id,
                self.missing_evidence.inventory_id,
                self.malformed_evidence.inventory_id,
                self.escalation_reasons.inventory_id,
                self.escalation_required,
                self.ACTIONIZER_NAME,
                self.ACTIONIZER_VERSION,
            ),
        )

    @property
    def candidate_order_id(self) -> str:
        """Return the exact candidate evaluated by this result."""
        return self.request.candidate_order_id

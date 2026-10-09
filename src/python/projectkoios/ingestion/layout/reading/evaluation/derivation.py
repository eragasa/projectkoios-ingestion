"""Pure derivation for replicated reading-order evaluation."""

from __future__ import annotations

from .alignment import (
    LayoutReadingOrderCandidateContradiction,
    LayoutReadingOrderCandidateContradictionInventory,
    LayoutReadingOrderReplicaAlignment,
    LayoutReadingOrderReplicaAlignmentInventory,
)
from .disagreement import (
    LayoutReadingOrderReplicaDisagreementPair,
    LayoutReadingOrderReplicaDisagreementPairInventory,
)
from .identity import LayoutReadingOrderReplicaEvidenceIdentityInventory
from .judgment import (
    LayoutReadingOrderNormalizedReplicaJudgment,
    LayoutReadingOrderReplicaJudgmentKind,
)
from .malformed import (
    LayoutReadingOrderMalformedReplicaEvidence,
    LayoutReadingOrderMalformedReplicaEvidenceInventory,
    LayoutReadingOrderMalformedReplicaReason,
    LayoutReadingOrderMalformedReplicaReasonInventory,
)
from .missing import (
    LayoutReadingOrderMissingReplicaEvidence,
    LayoutReadingOrderMissingReplicaEvidenceInventory,
)
from .reason import (
    LayoutReadingOrderEvaluationEscalationReason,
    LayoutReadingOrderEvaluationEscalationReasonInventory,
)
from .request import LayoutReadingOrderEvaluationRequest
from .status import (
    LayoutReadingOrderAggregateCoverage,
    LayoutReadingOrderReplicaAgreement,
)

_LayoutReadingOrderEvaluationDerivation = tuple[
    LayoutReadingOrderReplicaAgreement,
    LayoutReadingOrderAggregateCoverage,
    LayoutReadingOrderReplicaEvidenceIdentityInventory,
    LayoutReadingOrderReplicaEvidenceIdentityInventory,
    LayoutReadingOrderReplicaAlignmentInventory,
    LayoutReadingOrderReplicaDisagreementPairInventory,
    LayoutReadingOrderMissingReplicaEvidenceInventory,
    LayoutReadingOrderMalformedReplicaEvidenceInventory,
    LayoutReadingOrderEvaluationEscalationReasonInventory,
]


def derive_layout_reading_order_evaluation(
    *, request: LayoutReadingOrderEvaluationRequest
) -> _LayoutReadingOrderEvaluationDerivation:
    """Derive all evaluation dimensions without selecting an order."""
    candidate = tuple(request.candidate)
    candidate_set = set(candidate)
    present = tuple(
        slot for slot in request.replica_slots if slot.judgment is not None
    )
    evidence_identity_counts: dict[str, int] = {}
    for slot in present:
        judgment = slot.judgment
        if (
            judgment is None
            or not judgment.normalized_replica_evidence_id.strip()
        ):
            continue
        identity = judgment.normalized_replica_evidence_id
        evidence_identity_counts[identity] = (
            evidence_identity_counts.get(identity, 0) + 1
        )

    malformed_values: list[LayoutReadingOrderMalformedReplicaEvidence] = []
    valid_slots = []
    for slot in present:
        judgment = slot.judgment
        if judgment is None:
            raise RuntimeError("present replica slot omitted its judgment")
        malformed_reasons = list(
            derive_layout_reading_order_malformed_reasons(
                judgment=judgment,
                candidate_order_id=request.candidate_order_id,
                candidate=candidate,
                candidate_set=candidate_set,
            )
        )
        if (
            judgment.normalized_replica_evidence_id.strip()
            and evidence_identity_counts[
                judgment.normalized_replica_evidence_id
            ]
            > 1
        ):
            malformed_reasons.append(
                LayoutReadingOrderMalformedReplicaReason.DUPLICATE_NORMALIZED_REPLICA_EVIDENCE_ID
            )
        unique_reasons = tuple(sorted(set(malformed_reasons), key=str))
        if unique_reasons:
            malformed_values.append(
                LayoutReadingOrderMalformedReplicaEvidence(
                    replica_index=slot.replica_index,
                    normalized_replica_evidence_id=(
                        judgment.normalized_replica_evidence_id
                    ),
                    reasons=LayoutReadingOrderMalformedReplicaReasonInventory(
                        *unique_reasons
                    ),
                )
            )
        else:
            valid_slots.append(slot)

    missing = LayoutReadingOrderMissingReplicaEvidenceInventory(
        *(
            LayoutReadingOrderMissingReplicaEvidence(
                replica_index=slot.replica_index
            )
            for slot in request.replica_slots
            if slot.judgment is None
        )
    )
    malformed = LayoutReadingOrderMalformedReplicaEvidenceInventory(
        *malformed_values
    )
    alignments = LayoutReadingOrderReplicaAlignmentInventory(
        *(
            derive_layout_reading_order_replica_alignment(
                replica_index=slot.replica_index,
                judgment=slot.judgment,
                candidate=candidate,
            )
            for slot in valid_slots
            if slot.judgment is not None
        )
    )
    considered = LayoutReadingOrderReplicaEvidenceIdentityInventory(
        *sorted(
            {
                slot.judgment.normalized_replica_evidence_id
                for slot in present
                if slot.judgment is not None
                and slot.judgment.normalized_replica_evidence_id.strip()
            }
        )
    )
    valid = LayoutReadingOrderReplicaEvidenceIdentityInventory(
        *sorted(
            alignment.normalized_replica_evidence_id for alignment in alignments
        )
    )
    disagreements = derive_layout_reading_order_replica_disagreements(
        candidate=candidate,
        alignments=alignments,
    )
    coverage = derive_layout_reading_order_aggregate_coverage(
        candidate_set=candidate_set,
        expected_replica_count=len(request.replica_slots),
        alignments=alignments,
    )
    agreement = derive_layout_reading_order_replica_agreement(
        candidate_set=candidate_set,
        alignments=alignments,
        disagreements=disagreements,
    )
    reasons = derive_layout_reading_order_escalation_reasons(
        coverage=coverage,
        agreement=agreement,
        alignments=alignments,
        missing=missing,
        malformed=malformed,
    )
    return (
        agreement,
        coverage,
        considered,
        valid,
        alignments,
        disagreements,
        missing,
        malformed,
        reasons,
    )


def derive_layout_reading_order_malformed_reasons(
    *,
    judgment: LayoutReadingOrderNormalizedReplicaJudgment,
    candidate_order_id: str,
    candidate: tuple[str, ...],
    candidate_set: set[str],
) -> tuple[LayoutReadingOrderMalformedReplicaReason, ...]:
    """Derive exact structural and semantic faults for one normalized record."""
    reasons: list[LayoutReadingOrderMalformedReplicaReason] = []
    covered = tuple(judgment.covered_elements)
    claimed = (
        None
        if judgment.claimed_order is None
        else tuple(judgment.claimed_order)
    )
    if not judgment.normalized_replica_evidence_id.strip():
        reasons.append(
            LayoutReadingOrderMalformedReplicaReason.EMPTY_NORMALIZED_REPLICA_EVIDENCE_ID
        )
    if judgment.candidate_order_id != candidate_order_id:
        reasons.append(
            LayoutReadingOrderMalformedReplicaReason.WRONG_CANDIDATE_ORDER
        )
    if any(not element_id for element_id in covered):
        reasons.append(
            LayoutReadingOrderMalformedReplicaReason.EMPTY_COVERED_ELEMENT_ID
        )
    if any(element_id not in candidate_set for element_id in covered):
        reasons.append(
            LayoutReadingOrderMalformedReplicaReason.UNKNOWN_COVERED_ELEMENT_ID
        )
    if len(covered) != len(set(covered)):
        reasons.append(
            LayoutReadingOrderMalformedReplicaReason.DUPLICATE_COVERED_ELEMENT_ID
        )
    if claimed is not None:
        if any(not element_id for element_id in claimed):
            reasons.append(
                LayoutReadingOrderMalformedReplicaReason.EMPTY_CLAIMED_ELEMENT_ID
            )
        if any(element_id not in candidate_set for element_id in claimed):
            reasons.append(
                LayoutReadingOrderMalformedReplicaReason.UNKNOWN_CLAIMED_ELEMENT_ID
            )
        if len(claimed) != len(set(claimed)):
            reasons.append(
                LayoutReadingOrderMalformedReplicaReason.DUPLICATE_CLAIMED_ELEMENT_ID
            )
        if len(claimed) != len(covered) or set(claimed) != set(covered):
            reasons.append(
                LayoutReadingOrderMalformedReplicaReason.CLAIMED_ORDER_COVERAGE_MISMATCH
            )
    expected = tuple(
        element_id for element_id in candidate if element_id in set(covered)
    )
    if judgment.judgment is LayoutReadingOrderReplicaJudgmentKind.UNRESOLVED:
        if claimed is not None:
            reasons.append(
                LayoutReadingOrderMalformedReplicaReason.CLAIMED_ORDER_FORBIDDEN
            )
    elif claimed is None:
        reasons.append(
            LayoutReadingOrderMalformedReplicaReason.CLAIMED_ORDER_REQUIRED
        )
    elif (
        judgment.judgment
        is LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE
    ):
        if claimed != expected:
            reasons.append(
                LayoutReadingOrderMalformedReplicaReason.DECLARED_AGREEMENT_MISMATCH
            )
    elif claimed == expected:
        reasons.append(
            LayoutReadingOrderMalformedReplicaReason.DECLARED_DISAGREEMENT_MISMATCH
        )
    return tuple(reasons)


def derive_layout_reading_order_replica_alignment(
    *,
    replica_index: int,
    judgment: LayoutReadingOrderNormalizedReplicaJudgment,
    candidate: tuple[str, ...],
) -> LayoutReadingOrderReplicaAlignment:
    """Derive candidate contradictions for one valid normalized judgment."""
    claimed = (
        () if judgment.claimed_order is None else tuple(judgment.claimed_order)
    )
    positions = {element_id: index for index, element_id in enumerate(claimed)}
    contradictions: list[LayoutReadingOrderCandidateContradiction] = []
    for first_index, first_id in enumerate(candidate):
        if first_id not in positions:
            continue
        for second_id in candidate[first_index + 1 :]:
            if (
                second_id in positions
                and positions[first_id] > positions[second_id]
            ):
                contradictions.append(
                    LayoutReadingOrderCandidateContradiction(
                        claimed_before_element_id=second_id,
                        claimed_after_element_id=first_id,
                    )
                )
    return LayoutReadingOrderReplicaAlignment(
        replica_index=replica_index,
        normalized_replica_evidence_id=judgment.normalized_replica_evidence_id,
        judgment=judgment.judgment,
        covered_elements=judgment.covered_elements,
        claimed_order=judgment.claimed_order,
        contradictions=LayoutReadingOrderCandidateContradictionInventory(
            *contradictions
        ),
    )


def derive_layout_reading_order_replica_disagreements(
    *,
    candidate: tuple[str, ...],
    alignments: LayoutReadingOrderReplicaAlignmentInventory,
) -> LayoutReadingOrderReplicaDisagreementPairInventory:
    """Derive every candidate-oriented pair claimed in opposite directions."""
    pairs: list[LayoutReadingOrderReplicaDisagreementPair] = []
    positions = {
        alignment.normalized_replica_evidence_id: (
            {}
            if alignment.claimed_order is None
            else {
                element_id: index
                for index, element_id in enumerate(alignment.claimed_order)
            }
        )
        for alignment in alignments
    }
    for first_index, first_id in enumerate(candidate):
        for second_id in candidate[first_index + 1 :]:
            forward: list[str] = []
            reverse: list[str] = []
            for evidence_id, order_positions in positions.items():
                if (
                    first_id not in order_positions
                    or second_id not in order_positions
                ):
                    continue
                if order_positions[first_id] < order_positions[second_id]:
                    forward.append(evidence_id)
                else:
                    reverse.append(evidence_id)
            if forward and reverse:
                pairs.append(
                    LayoutReadingOrderReplicaDisagreementPair(
                        candidate_first_element_id=first_id,
                        candidate_second_element_id=second_id,
                        forward_evidence_ids=LayoutReadingOrderReplicaEvidenceIdentityInventory(
                            *sorted(forward)
                        ),
                        reverse_evidence_ids=LayoutReadingOrderReplicaEvidenceIdentityInventory(
                            *sorted(reverse)
                        ),
                    )
                )
    return LayoutReadingOrderReplicaDisagreementPairInventory(*pairs)


def derive_layout_reading_order_aggregate_coverage(
    *,
    candidate_set: set[str],
    expected_replica_count: int,
    alignments: LayoutReadingOrderReplicaAlignmentInventory,
) -> LayoutReadingOrderAggregateCoverage:
    """Derive conservative coverage across every declared replica slot."""
    covered_sets = tuple(
        set(alignment.covered_elements) for alignment in alignments
    )
    if len(alignments) == expected_replica_count and all(
        covered == candidate_set for covered in covered_sets
    ):
        return LayoutReadingOrderAggregateCoverage.COMPLETE
    if not any(covered_sets):
        return LayoutReadingOrderAggregateCoverage.NONE
    return LayoutReadingOrderAggregateCoverage.PARTIAL


def derive_layout_reading_order_replica_agreement(
    *,
    candidate_set: set[str],
    alignments: LayoutReadingOrderReplicaAlignmentInventory,
    disagreements: LayoutReadingOrderReplicaDisagreementPairInventory,
) -> LayoutReadingOrderReplicaAgreement:
    """Derive exact, partial, conflicting, or unevaluable replica agreement."""
    if len(alignments) < 2:
        return LayoutReadingOrderReplicaAgreement.NOT_EVALUABLE
    if len(disagreements) != 0:
        return LayoutReadingOrderReplicaAgreement.DISAGREEMENT
    semantic_values = {
        (
            alignment.judgment,
            frozenset(alignment.covered_elements),
            (
                None
                if alignment.claimed_order is None
                else tuple(alignment.claimed_order)
            ),
        )
        for alignment in alignments
    }
    if len(semantic_values) == 1 and all(
        set(alignment.covered_elements) == candidate_set
        for alignment in alignments
    ):
        return LayoutReadingOrderReplicaAgreement.EXACT_AGREEMENT
    return LayoutReadingOrderReplicaAgreement.CONSISTENT_PARTIAL


def derive_layout_reading_order_escalation_reasons(
    *,
    coverage: LayoutReadingOrderAggregateCoverage,
    agreement: LayoutReadingOrderReplicaAgreement,
    alignments: LayoutReadingOrderReplicaAlignmentInventory,
    missing: LayoutReadingOrderMissingReplicaEvidenceInventory,
    malformed: LayoutReadingOrderMalformedReplicaEvidenceInventory,
) -> LayoutReadingOrderEvaluationEscalationReasonInventory:
    """Derive the closed conservative escalation reason set."""
    reasons: set[LayoutReadingOrderEvaluationEscalationReason] = set()
    if len(alignments) < 2:
        reasons.add(
            LayoutReadingOrderEvaluationEscalationReason.TOO_FEW_DISTINCT_VALID_REPLICAS
        )
    if len(missing) != 0:
        reasons.add(
            LayoutReadingOrderEvaluationEscalationReason.MISSING_EVIDENCE
        )
    if len(malformed) != 0:
        reasons.add(
            LayoutReadingOrderEvaluationEscalationReason.MALFORMED_EVIDENCE
        )
    if coverage is not LayoutReadingOrderAggregateCoverage.COMPLETE:
        reasons.add(
            LayoutReadingOrderEvaluationEscalationReason.INCOMPLETE_COVERAGE
        )
    if any(
        alignment.judgment is LayoutReadingOrderReplicaJudgmentKind.UNRESOLVED
        for alignment in alignments
    ):
        reasons.add(
            LayoutReadingOrderEvaluationEscalationReason.UNRESOLVED_JUDGMENT
        )
    if agreement is LayoutReadingOrderReplicaAgreement.DISAGREEMENT:
        reasons.add(
            LayoutReadingOrderEvaluationEscalationReason.REPLICA_DISAGREEMENT
        )
    if any(
        alignment.judgment
        is LayoutReadingOrderReplicaJudgmentKind.DISAGREES_WITH_CANDIDATE
        for alignment in alignments
    ):
        reasons.add(
            LayoutReadingOrderEvaluationEscalationReason.CANDIDATE_DISPUTED
        )
    return LayoutReadingOrderEvaluationEscalationReasonInventory(
        *sorted(reasons, key=str)
    )

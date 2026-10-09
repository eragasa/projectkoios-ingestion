from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.ingestion.layout.reading.evaluation.actionizer import (
    LayoutReadingOrderEvaluationActionizer,
)
from projectkoios.ingestion.layout.reading.evaluation.judgment import (
    LayoutReadingOrderNormalizedReplicaJudgment,
    LayoutReadingOrderReplicaJudgmentKind,
)
from projectkoios.ingestion.layout.reading.evaluation.limits import (
    MAX_LAYOUT_READING_ORDER_EVALUATION_RELATIONS,
)
from projectkoios.ingestion.layout.reading.evaluation.malformed import (
    LayoutReadingOrderMalformedReplicaReason,
)
from projectkoios.ingestion.layout.reading.evaluation.reason import (
    LayoutReadingOrderEvaluationEscalationReason,
)
from projectkoios.ingestion.layout.reading.evaluation.request import (
    LayoutReadingOrderEvaluationRequest,
)
from projectkoios.ingestion.layout.reading.evaluation.result import (
    LayoutReadingOrderEvaluationResult,
)
from projectkoios.ingestion.layout.reading.evaluation.sequence import (
    LayoutReadingOrderNormalizedElementSequence,
)
from projectkoios.ingestion.layout.reading.evaluation.slot import (
    LayoutReadingOrderReplicaJudgmentSlot,
    LayoutReadingOrderReplicaJudgmentSlotInventory,
)
from projectkoios.ingestion.layout.reading.evaluation.status import (
    LayoutReadingOrderAggregateCoverage,
    LayoutReadingOrderReplicaAgreement,
)
from projectkoios.ingestion.layout.reading.order.candidate import (
    LayoutReadingOrderCandidate,
)


def _judgment(
    *,
    candidate: LayoutReadingOrderCandidate,
    evidence_id: str,
    covered: tuple[str, ...],
    claimed: tuple[str, ...] | None,
    kind: LayoutReadingOrderReplicaJudgmentKind,
    candidate_order_id: str | None = None,
) -> LayoutReadingOrderNormalizedReplicaJudgment:
    return LayoutReadingOrderNormalizedReplicaJudgment(
        normalized_replica_evidence_id=evidence_id,
        candidate_order_id=(
            candidate.candidate_id
            if candidate_order_id is None
            else candidate_order_id
        ),
        covered_elements=LayoutReadingOrderNormalizedElementSequence(*covered),
        claimed_order=(
            None
            if claimed is None
            else LayoutReadingOrderNormalizedElementSequence(*claimed)
        ),
        judgment=kind,
    )


def _request(
    *judgments: LayoutReadingOrderNormalizedReplicaJudgment | None,
    candidate: LayoutReadingOrderCandidate | None = None,
) -> LayoutReadingOrderEvaluationRequest:
    selected_candidate = candidate or LayoutReadingOrderCandidate("a", "b", "c")
    return LayoutReadingOrderEvaluationRequest(
        candidate=selected_candidate,
        search_evidence_id="search-evidence:opaque:test",
        replica_slots=LayoutReadingOrderReplicaJudgmentSlotInventory(
            *(
                LayoutReadingOrderReplicaJudgmentSlot(
                    replica_index=index,
                    judgment=judgment,
                )
                for index, judgment in enumerate(judgments)
            )
        ),
    )


def _evaluate(
    request: LayoutReadingOrderEvaluationRequest,
) -> LayoutReadingOrderEvaluationResult:
    return LayoutReadingOrderEvaluationActionizer().action(request=request)


def test__two_complete_agreeing_replicas_are_the_only_non_escalated_case() -> (
    None
):
    candidate = LayoutReadingOrderCandidate("a", "b", "c")
    request = _request(
        _judgment(
            candidate=candidate,
            evidence_id="agent-normalized:replica-1",
            covered=("a", "b", "c"),
            claimed=("a", "b", "c"),
            kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
        ),
        _judgment(
            candidate=candidate,
            evidence_id="agent-normalized:replica-2",
            covered=("c", "a", "b"),
            claimed=("a", "b", "c"),
            kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
        ),
        candidate=candidate,
    )

    result = _evaluate(request)

    assert result.candidate_order_id == candidate.candidate_id
    assert (
        result.replica_agreement
        is LayoutReadingOrderReplicaAgreement.EXACT_AGREEMENT
    )
    assert (
        result.aggregate_coverage
        is LayoutReadingOrderAggregateCoverage.COMPLETE
    )
    assert tuple(result.considered_evidence_ids) == (
        "agent-normalized:replica-1",
        "agent-normalized:replica-2",
    )
    assert tuple(result.valid_evidence_ids) == tuple(
        result.considered_evidence_ids
    )
    assert len(result.disagreement_pairs) == 0
    assert len(result.missing_evidence) == 0
    assert len(result.malformed_evidence) == 0
    assert tuple(result.escalation_reasons) == ()
    assert result.escalation_required is False
    assert _evaluate(request).result_id == result.result_id
    assert not hasattr(result, "accepted_order")
    assert not hasattr(result, "corrected_order")
    assert not hasattr(result, "accuracy")


def test__conflicting_complete_replicas_report_exact_pair_disagreement() -> (
    None
):
    candidate = LayoutReadingOrderCandidate("a", "b", "c")
    request = _request(
        _judgment(
            candidate=candidate,
            evidence_id="agent-normalized:forward",
            covered=("a", "b", "c"),
            claimed=("a", "b", "c"),
            kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
        ),
        _judgment(
            candidate=candidate,
            evidence_id="agent-normalized:reverse",
            covered=("a", "b", "c"),
            claimed=("b", "a", "c"),
            kind=LayoutReadingOrderReplicaJudgmentKind.DISAGREES_WITH_CANDIDATE,
        ),
        candidate=candidate,
    )

    result = _evaluate(request)

    assert (
        result.replica_agreement
        is LayoutReadingOrderReplicaAgreement.DISAGREEMENT
    )
    assert (
        result.aggregate_coverage
        is LayoutReadingOrderAggregateCoverage.COMPLETE
    )
    disagreements = tuple(result.disagreement_pairs)
    assert len(disagreements) == 1
    assert disagreements[0].candidate_first_element_id == "a"
    assert disagreements[0].candidate_second_element_id == "b"
    assert tuple(disagreements[0].forward_evidence_ids) == (
        "agent-normalized:forward",
    )
    assert tuple(disagreements[0].reverse_evidence_ids) == (
        "agent-normalized:reverse",
    )
    assert set(result.escalation_reasons) == {
        LayoutReadingOrderEvaluationEscalationReason.REPLICA_DISAGREEMENT,
        LayoutReadingOrderEvaluationEscalationReason.CANDIDATE_DISPUTED,
    }


def test__majority_never_overrides_one_conflicting_valid_replica() -> None:
    candidate = LayoutReadingOrderCandidate("a", "b", "c")
    forward = tuple(
        _judgment(
            candidate=candidate,
            evidence_id=f"agent-normalized:majority-{index}",
            covered=("a", "b", "c"),
            claimed=("a", "b", "c"),
            kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
        )
        for index in (1, 2)
    )
    reverse = _judgment(
        candidate=candidate,
        evidence_id="agent-normalized:minority",
        covered=("a", "b", "c"),
        claimed=("b", "a", "c"),
        kind=LayoutReadingOrderReplicaJudgmentKind.DISAGREES_WITH_CANDIDATE,
    )

    result = _evaluate(_request(*forward, reverse, candidate=candidate))

    assert (
        result.replica_agreement
        is LayoutReadingOrderReplicaAgreement.DISAGREEMENT
    )
    assert (
        LayoutReadingOrderEvaluationEscalationReason.REPLICA_DISAGREEMENT
        in set(result.escalation_reasons)
    )


def test__unanimous_alternative_is_exact_replica_agreement_but_escalates() -> (
    None
):
    candidate = LayoutReadingOrderCandidate("a", "b", "c")
    alternative = ("b", "a", "c")
    request = _request(
        *(
            _judgment(
                candidate=candidate,
                evidence_id=f"agent-normalized:alternative-{index}",
                covered=("a", "b", "c"),
                claimed=alternative,
                kind=LayoutReadingOrderReplicaJudgmentKind.DISAGREES_WITH_CANDIDATE,
            )
            for index in (1, 2)
        ),
        candidate=candidate,
    )

    result = _evaluate(request)

    assert (
        result.replica_agreement
        is LayoutReadingOrderReplicaAgreement.EXACT_AGREEMENT
    )
    assert (
        result.aggregate_coverage
        is LayoutReadingOrderAggregateCoverage.COMPLETE
    )
    assert tuple(result.escalation_reasons) == (
        LayoutReadingOrderEvaluationEscalationReason.CANDIDATE_DISPUTED,
    )
    assert result.escalation_required is True


def test__consistent_partial_common_coverage_is_not_exact_agreement() -> None:
    candidate = LayoutReadingOrderCandidate("a", "b", "c")
    request = _request(
        _judgment(
            candidate=candidate,
            evidence_id="agent-normalized:partial-1",
            covered=("a", "b"),
            claimed=("a", "b"),
            kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
        ),
        _judgment(
            candidate=candidate,
            evidence_id="agent-normalized:partial-2",
            covered=("b", "c"),
            claimed=("b", "c"),
            kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
        ),
        candidate=candidate,
    )

    result = _evaluate(request)

    assert (
        result.replica_agreement
        is LayoutReadingOrderReplicaAgreement.CONSISTENT_PARTIAL
    )
    assert (
        result.aggregate_coverage is LayoutReadingOrderAggregateCoverage.PARTIAL
    )
    assert tuple(result.escalation_reasons) == (
        LayoutReadingOrderEvaluationEscalationReason.INCOMPLETE_COVERAGE,
    )


def test__complete_unresolved_replica_agreement_remains_escalated() -> None:
    candidate = LayoutReadingOrderCandidate("a", "b", "c")
    request = _request(
        *(
            _judgment(
                candidate=candidate,
                evidence_id=f"agent-normalized:unresolved-{index}",
                covered=("a", "b", "c"),
                claimed=None,
                kind=LayoutReadingOrderReplicaJudgmentKind.UNRESOLVED,
            )
            for index in (1, 2)
        ),
        candidate=candidate,
    )

    result = _evaluate(request)

    assert (
        result.replica_agreement
        is LayoutReadingOrderReplicaAgreement.EXACT_AGREEMENT
    )
    assert (
        result.aggregate_coverage
        is LayoutReadingOrderAggregateCoverage.COMPLETE
    )
    assert tuple(result.escalation_reasons) == (
        LayoutReadingOrderEvaluationEscalationReason.UNRESOLVED_JUDGMENT,
    )


def test__missing_slot_is_reported_without_manufacturing_replica_evidence() -> (
    None
):
    candidate = LayoutReadingOrderCandidate("a", "b", "c")
    request = _request(
        _judgment(
            candidate=candidate,
            evidence_id="agent-normalized:only",
            covered=("a", "b", "c"),
            claimed=("a", "b", "c"),
            kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
        ),
        None,
        candidate=candidate,
    )

    result = _evaluate(request)

    assert (
        result.replica_agreement
        is LayoutReadingOrderReplicaAgreement.NOT_EVALUABLE
    )
    assert (
        result.aggregate_coverage is LayoutReadingOrderAggregateCoverage.PARTIAL
    )
    assert tuple(item.replica_index for item in result.missing_evidence) == (1,)
    assert set(result.escalation_reasons) == {
        LayoutReadingOrderEvaluationEscalationReason.TOO_FEW_DISTINCT_VALID_REPLICAS,
        LayoutReadingOrderEvaluationEscalationReason.MISSING_EVIDENCE,
        LayoutReadingOrderEvaluationEscalationReason.INCOMPLETE_COVERAGE,
    }


@pytest.mark.parametrize(
    ("malformed", "expected_reason"),
    (
        (
            "declared-mismatch",
            LayoutReadingOrderMalformedReplicaReason.DECLARED_AGREEMENT_MISMATCH,
        ),
        (
            "wrong-candidate",
            LayoutReadingOrderMalformedReplicaReason.WRONG_CANDIDATE_ORDER,
        ),
    ),
)
def test__malformed_normalized_semantics_are_reported(
    malformed: str,
    expected_reason: LayoutReadingOrderMalformedReplicaReason,
) -> None:
    candidate = LayoutReadingOrderCandidate("a", "b", "c")
    first = _judgment(
        candidate=candidate,
        evidence_id="agent-normalized:malformed",
        covered=("a", "b", "c"),
        claimed=("b", "a", "c")
        if malformed == "declared-mismatch"
        else ("a", "b", "c"),
        kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
        candidate_order_id=(
            "wrong-candidate" if malformed == "wrong-candidate" else None
        ),
    )
    second = _judgment(
        candidate=candidate,
        evidence_id="agent-normalized:valid",
        covered=("a", "b", "c"),
        claimed=("a", "b", "c"),
        kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
    )

    result = _evaluate(_request(first, second, candidate=candidate))

    assert (
        result.replica_agreement
        is LayoutReadingOrderReplicaAgreement.NOT_EVALUABLE
    )
    malformed_evidence = tuple(result.malformed_evidence)
    assert len(malformed_evidence) == 1
    assert expected_reason in set(malformed_evidence[0].reasons)
    assert set(result.escalation_reasons) == {
        LayoutReadingOrderEvaluationEscalationReason.TOO_FEW_DISTINCT_VALID_REPLICAS,
        LayoutReadingOrderEvaluationEscalationReason.MALFORMED_EVIDENCE,
        LayoutReadingOrderEvaluationEscalationReason.INCOMPLETE_COVERAGE,
    }


def test__empty_identity_and_duplicate_elements_are_malformed() -> None:
    candidate = LayoutReadingOrderCandidate("a", "b", "c")
    malformed = _judgment(
        candidate=candidate,
        evidence_id="",
        covered=("a", "a"),
        claimed=("a", "a"),
        kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
    )
    valid = _judgment(
        candidate=candidate,
        evidence_id="agent-normalized:valid",
        covered=("a", "b", "c"),
        claimed=("a", "b", "c"),
        kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
    )

    result = _evaluate(_request(malformed, valid, candidate=candidate))

    reasons = set(tuple(result.malformed_evidence)[0].reasons)
    assert reasons >= {
        LayoutReadingOrderMalformedReplicaReason.EMPTY_NORMALIZED_REPLICA_EVIDENCE_ID,
        LayoutReadingOrderMalformedReplicaReason.DUPLICATE_COVERED_ELEMENT_ID,
        LayoutReadingOrderMalformedReplicaReason.DUPLICATE_CLAIMED_ELEMENT_ID,
    }
    assert tuple(result.considered_evidence_ids) == ("agent-normalized:valid",)


def test__duplicate_replica_evidence_identity_invalidates_every_duplicate() -> (
    None
):
    candidate = LayoutReadingOrderCandidate("a", "b", "c")
    judgments = tuple(
        _judgment(
            candidate=candidate,
            evidence_id="agent-normalized:duplicate",
            covered=("a", "b", "c"),
            claimed=("a", "b", "c"),
            kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
        )
        for _ in range(2)
    )

    result = _evaluate(_request(*judgments, candidate=candidate))

    assert (
        result.replica_agreement
        is LayoutReadingOrderReplicaAgreement.NOT_EVALUABLE
    )
    assert result.aggregate_coverage is LayoutReadingOrderAggregateCoverage.NONE
    assert tuple(result.considered_evidence_ids) == (
        "agent-normalized:duplicate",
    )
    assert tuple(result.valid_evidence_ids) == ()
    assert len(result.malformed_evidence) == 2
    assert all(
        LayoutReadingOrderMalformedReplicaReason.DUPLICATE_NORMALIZED_REPLICA_EVIDENCE_ID
        in set(item.reasons)
        for item in result.malformed_evidence
    )


def test__result_rederives_all_fields_and_rejects_forged_status() -> None:
    candidate = LayoutReadingOrderCandidate("a", "b")
    request = _request(
        *(
            _judgment(
                candidate=candidate,
                evidence_id=f"agent-normalized:replica-{index}",
                covered=("a", "b"),
                claimed=("a", "b"),
                kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
            )
            for index in (1, 2)
        ),
        candidate=candidate,
    )
    result = _evaluate(request)

    with pytest.raises(ValueError, match="differs from derivation"):
        replace(
            result,
            replica_agreement=LayoutReadingOrderReplicaAgreement.DISAGREEMENT,
        )


def test__request_accepts_the_exact_relation_budget_boundary() -> None:
    candidate = LayoutReadingOrderCandidate(
        *(f"element-{index}" for index in range(316))
    )
    relation_count = 2 * len(candidate) * (len(candidate) - 1) // 2

    request = _request(None, None, candidate=candidate)

    assert relation_count <= MAX_LAYOUT_READING_ORDER_EVALUATION_RELATIONS
    assert request.candidate is candidate


def test__request_rejects_worst_case_relations_above_budget() -> None:
    candidate = LayoutReadingOrderCandidate(
        *(f"element-{index}" for index in range(317))
    )
    relation_count = 2 * len(candidate) * (len(candidate) - 1) // 2

    assert relation_count > MAX_LAYOUT_READING_ORDER_EVALUATION_RELATIONS
    with pytest.raises(ValueError, match="relation budget exceeded"):
        _request(None, None, candidate=candidate)


def test__normalized_sequence_accepts_owner_valid_layout_identity_length() -> (
    None
):
    long_element_id = "x" * 600
    candidate = LayoutReadingOrderCandidate(long_element_id, "short")
    judgments = tuple(
        _judgment(
            candidate=candidate,
            evidence_id=f"agent-normalized:long-{index}",
            covered=(long_element_id, "short"),
            claimed=(long_element_id, "short"),
            kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
        )
        for index in (1, 2)
    )

    result = _evaluate(_request(*judgments, candidate=candidate))

    assert result.escalation_required is False


def test__normalized_sequence_accepts_owner_valid_control_characters() -> None:
    control_element_id = "\n"
    candidate = LayoutReadingOrderCandidate(control_element_id, "region-2")
    judgments = tuple(
        _judgment(
            candidate=candidate,
            evidence_id=f"agent-normalized:control-{index}",
            covered=(control_element_id, "region-2"),
            claimed=(control_element_id, "region-2"),
            kind=LayoutReadingOrderReplicaJudgmentKind.AGREES_WITH_CANDIDATE,
        )
        for index in (1, 2)
    )

    result = _evaluate(_request(*judgments, candidate=candidate))

    assert result.escalation_required is False


def test__request_requires_one_candidate_with_at_least_two_elements() -> None:
    with pytest.raises(ValueError, match="at least two elements"):
        _request(None, None, candidate=LayoutReadingOrderCandidate("only"))

"""Deterministic local detector admission-gate tests."""

from dataclasses import replace

import pytest
from projectkoios.ingestion.integrations.coco.layout.actionizer import (
    CocoLayoutRegionProposalActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.detector.gate.actionizer import (  # noqa: E501
    CocoLayoutDetectorGateActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.detector.gate.configuration import (  # noqa: E501
    CocoLayoutDetectorGateConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.detector.gate.reason import (  # noqa: E501
    CocoLayoutDetectorGateReason,
    CocoLayoutDetectorGateStatus,
)
from projectkoios.ingestion.integrations.coco.layout.detector.gate.request import (  # noqa: E501
    CocoLayoutDetectorGateRequest,
)
from projectkoios.ingestion.integrations.coco.layout.detector.gate.result import (  # noqa: E501
    CocoLayoutDetectorGateResult,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.actionizer import (  # noqa: E501
    CocoLayoutDetectorOutputParser,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.request import (  # noqa: E501
    CocoLayoutDetectorOutputParsingRequest,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.result import (  # noqa: E501
    CocoLayoutDetectorInvocationFailureKind,
    CocoLayoutDetectorInvocationResult,
    CocoLayoutDetectorInvocationStatus,
)
from projectkoios.ingestion.layout.review.actionizer import (
    DeterministicLayoutReviewActionizer,
)
from projectkoios.ingestion.layout.review.request import LayoutReviewRequest

from tests.projectkoios.ingestion.integrations.coco.layout.detector_fixture import (  # noqa: E501
    coco_layout_gate_request,
)


def test_gate_admits_complete_supported_deterministic_evidence() -> None:
    request = coco_layout_gate_request()
    result = CocoLayoutDetectorGateActionizer().action(request=request)

    assert result.status is CocoLayoutDetectorGateStatus.ADMITTED
    assert result.reasons == ()
    assert result.admitted_for_deterministic_finalization is True
    assert result == CocoLayoutDetectorGateActionizer().action(request=request)


@pytest.mark.parametrize(
    ("gate_request", "expected_reasons"),
    (
        (
            coco_layout_gate_request(include_limitations=True),
            (CocoLayoutDetectorGateReason.UNSUPPORTED_LABEL_OBSERVED,),
        ),
        (
            coco_layout_gate_request(omit_formula=True),
            (
                CocoLayoutDetectorGateReason.DETERMINISTIC_LAYOUT_REVIEW_REQUIRED,
            ),
        ),
        (
            coco_layout_gate_request(
                gate_configuration=CocoLayoutDetectorGateConfiguration(
                    minimum_accepted_detections=3
                )
            ),
            (CocoLayoutDetectorGateReason.INSUFFICIENT_ACCEPTED_DETECTIONS,),
        ),
        (
            coco_layout_gate_request(
                include_limitations=True,
                gate_configuration=CocoLayoutDetectorGateConfiguration(
                    maximum_limitations=0
                ),
            ),
            (
                CocoLayoutDetectorGateReason.LIMITATION_BOUND_EXCEEDED,
                CocoLayoutDetectorGateReason.UNSUPPORTED_LABEL_OBSERVED,
            ),
        ),
    ),
)
def test_gate_escalates_explicit_deterministic_failures(
    gate_request: CocoLayoutDetectorGateRequest,
    expected_reasons: tuple[CocoLayoutDetectorGateReason, ...],
) -> None:
    result = CocoLayoutDetectorGateActionizer().action(request=gate_request)

    assert result.status is CocoLayoutDetectorGateStatus.ESCALATION_REQUIRED
    assert result.reasons == expected_reasons
    assert result.admitted_for_deterministic_finalization is False


def test_gate_policy_may_retain_unsupported_label_as_nonblocking_evidence() -> (
    None
):
    request = coco_layout_gate_request(
        include_limitations=True,
        gate_configuration=CocoLayoutDetectorGateConfiguration(
            unsupported_labels_require_escalation=False
        ),
    )

    result = CocoLayoutDetectorGateActionizer().action(request=request)

    assert result.status is CocoLayoutDetectorGateStatus.ADMITTED
    assert result.reasons == ()


def test_gate_request_rejects_parsing_without_successful_invocation() -> None:
    exact = coco_layout_gate_request()
    invocation_request = exact.parsing_result.request.invocation.request
    failed_invocation = CocoLayoutDetectorInvocationResult(
        request=invocation_request,
        status=CocoLayoutDetectorInvocationStatus.FAILED,
        request_document_bytes=invocation_request.document_bytes(),
        raw_output_bytes=None,
        elapsed_nanoseconds=1,
        failure_kind=CocoLayoutDetectorInvocationFailureKind.RUNTIME,
        failure_code="fixture-runtime-failure",
    )
    invalid_parsing = CocoLayoutDetectorOutputParser().action(
        request=CocoLayoutDetectorOutputParsingRequest(
            invocation=failed_invocation
        )
    )

    with pytest.raises(ValueError, match="requires valid detector invocation"):
        CocoLayoutDetectorGateRequest(
            parsing_result=invalid_parsing,
            proposal_result=exact.proposal_result,
            review_case=exact.review_case,
            configuration=exact.configuration,
        )


def test_gate_request_rejects_mismatched_detector_and_proposal_results() -> (
    None
):
    complete = coco_layout_gate_request()
    incomplete = coco_layout_gate_request(omit_formula=True)

    with pytest.raises(ValueError, match="does not consume"):
        CocoLayoutDetectorGateRequest(
            parsing_result=incomplete.parsing_result,
            proposal_result=complete.proposal_result,
            review_case=complete.review_case,
            configuration=complete.configuration,
        )


def test_gate_request_rejects_forged_proposal_configuration() -> None:
    exact = coco_layout_gate_request()
    proposal_request = exact.proposal_result.request
    forged_result = CocoLayoutRegionProposalActionizer().action(
        request=replace(
            proposal_request,
            configuration=replace(
                proposal_request.configuration,
                max_detections=(
                    proposal_request.configuration.max_detections - 1
                ),
            ),
        )
    )
    review_case = DeterministicLayoutReviewActionizer().action(
        request=LayoutReviewRequest.create(
            layout=exact.review_case.request.layout,
            render=exact.review_case.request.render,
            proposal_source=forged_result.proposal_source,
            proposals=forged_result.proposals,
            configuration=exact.review_case.request.configuration,
        )
    )

    with pytest.raises(ValueError, match="configuration differs"):
        CocoLayoutDetectorGateRequest(
            parsing_result=exact.parsing_result,
            proposal_result=forged_result,
            review_case=review_case,
            configuration=exact.configuration,
        )


def test_gate_result_rejects_forged_admission() -> None:
    request = coco_layout_gate_request(include_limitations=True)

    with pytest.raises(ValueError, match="differs from deterministic"):
        CocoLayoutDetectorGateResult(
            request=request,
            status=CocoLayoutDetectorGateStatus.ADMITTED,
            reasons=(),
        )

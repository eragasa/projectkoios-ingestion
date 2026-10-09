"""Strict canonical local detector output parsing tests."""

import pytest
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.output import (  # noqa: E501
    CocoLayoutDetectorRawOutput,
    CocoLayoutDetectorRawOutputJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.actionizer import (  # noqa: E501
    CocoLayoutDetectorOutputParser,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.request import (  # noqa: E501
    CocoLayoutDetectorOutputParsingRequest,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.result import (  # noqa: E501
    CocoLayoutDetectorOutputParsingResult,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.status import (  # noqa: E501
    CocoLayoutDetectorOutputParsingStatus,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.result import (  # noqa: E501
    CocoLayoutDetectorInvocationFailureKind,
    CocoLayoutDetectorInvocationResult,
    CocoLayoutDetectorInvocationStatus,
)

from tests.projectkoios.ingestion.integrations.coco.layout.detector_fixture import (  # noqa: E501
    coco_layout_detector_raw_output,
    coco_layout_invocation_request,
)


def detector_invocation(
    raw_output_bytes: bytes,
) -> CocoLayoutDetectorInvocationResult:
    """Build one complete exact invocation around supplied raw bytes."""
    request = coco_layout_invocation_request()
    return CocoLayoutDetectorInvocationResult(
        request=request,
        status=CocoLayoutDetectorInvocationStatus.COMPLETE,
        request_document_bytes=request.document_bytes(),
        raw_output_bytes=raw_output_bytes,
        elapsed_nanoseconds=1,
        failure_kind=None,
        failure_code=None,
    )


def test_raw_output_contract_round_trips_exact_observation_order() -> None:
    output = coco_layout_detector_raw_output()
    contract = CocoLayoutDetectorRawOutputJsonContract()

    content = contract.serialize_bytes(output)

    assert contract.parse_bytes(content) == output
    assert contract.serialize_bytes(contract.parse_bytes(content)) == content


def test_output_parser_constructs_exact_detector_result() -> None:
    output = coco_layout_detector_raw_output()
    invocation = detector_invocation(
        CocoLayoutDetectorRawOutputJsonContract().serialize_bytes(output)
    )

    result = CocoLayoutDetectorOutputParser().action(
        request=CocoLayoutDetectorOutputParsingRequest(invocation=invocation)
    )

    assert result.status is CocoLayoutDetectorOutputParsingStatus.VALID
    assert result.raw_output == output
    assert result.detector_result is not None
    assert result.detector_result.request.observations == output.observations
    assert (
        result.detector_result.request.configuration
        == invocation.request.configuration
    )


def test_output_parser_rejects_noncanonical_raw_output() -> None:
    content = CocoLayoutDetectorRawOutputJsonContract().serialize_bytes(
        coco_layout_detector_raw_output()
    )

    result = CocoLayoutDetectorOutputParser().action(
        request=CocoLayoutDetectorOutputParsingRequest(
            invocation=detector_invocation(content + b" ")
        )
    )

    assert result.status is CocoLayoutDetectorOutputParsingStatus.INVALID
    assert result.failure_code == "detector_output_invalid"
    assert result.raw_output is None
    assert result.detector_result is None


def test_output_parser_rejects_stale_resource_binding() -> None:
    output = coco_layout_detector_raw_output()
    content = CocoLayoutDetectorRawOutputJsonContract().serialize_bytes(
        CocoLayoutDetectorRawOutput(
            render_id=output.render_id,
            resource_id="another-resource",
            preprocessing_id=output.preprocessing_id,
            observations=output.observations,
        )
    )

    result = CocoLayoutDetectorOutputParser().action(
        request=CocoLayoutDetectorOutputParsingRequest(
            invocation=detector_invocation(content)
        )
    )

    assert result.status is CocoLayoutDetectorOutputParsingStatus.INVALID
    assert result.failure_code == "detector_output_invalid"


def test_parsing_result_rejects_forged_failure() -> None:
    invocation = detector_invocation(
        CocoLayoutDetectorRawOutputJsonContract().serialize_bytes(
            coco_layout_detector_raw_output()
        )
    )
    request = CocoLayoutDetectorOutputParsingRequest(invocation=invocation)

    with pytest.raises(ValueError, match="differs from exact derivation"):
        CocoLayoutDetectorOutputParsingResult(
            request=request,
            status=CocoLayoutDetectorOutputParsingStatus.INVALID,
            raw_output=None,
            detector_result=None,
            failure_code="detector_output_invalid",
        )


def test_output_parser_preserves_invocation_failure_boundary() -> None:
    request = coco_layout_invocation_request()
    invocation = CocoLayoutDetectorInvocationResult(
        request=request,
        status=CocoLayoutDetectorInvocationStatus.FAILED,
        request_document_bytes=request.document_bytes(),
        raw_output_bytes=None,
        elapsed_nanoseconds=1,
        failure_kind=CocoLayoutDetectorInvocationFailureKind.RUNTIME,
        failure_code="runtime-failed",
    )

    result = CocoLayoutDetectorOutputParser().action(
        request=CocoLayoutDetectorOutputParsingRequest(invocation=invocation)
    )

    assert (
        result.status is CocoLayoutDetectorOutputParsingStatus.INVOCATION_FAILED
    )
    assert result.failure_code == "detector_invocation_failed"

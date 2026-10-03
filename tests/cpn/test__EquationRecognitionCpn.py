from __future__ import annotations

from projectkoios.ingestion.equations.recognition.error import (
    EquationRecognitionError,
)

from cpn.equation_recognition import (
    build_equation_recognition_net,
    project_equation_recognition_request,
    record_equation_recognition_failure,
    record_equation_recognition_result,
)
from tests.equation_recognition_derivation_support import (
    artifact,
    assembly,
    processor,
)
from workflow.equation_recognition import (
    plan_equation_recognition,
    record_equation_recognition_derivation,
)
from workflow.equation_recognition import (
    record_equation_recognition_failure as workflow_failure,
)


def test__equation_recognition_cpn__shadows_workflow_request() -> None:
    recognition_assembly = assembly()
    recognition_processor = processor()
    expected = plan_equation_recognition(
        assembly=recognition_assembly,
        processor=recognition_processor,
    )
    net = build_equation_recognition_net(
        recognition_assembly,
        recognition_processor,
    )

    observed = project_equation_recognition_request(net)

    assert observed == expected


def test__equation_recognition_cpn__shadows_correlated_success_trace() -> None:
    net = build_equation_recognition_net(assembly(), processor())
    request = project_equation_recognition_request(net)
    recognition = artifact(recognition_request=request)
    expected = record_equation_recognition_derivation(
        request=request,
        result=recognition,
    )

    observed = record_equation_recognition_result(net, recognition)

    assert observed == expected
    assert observed.trace.trace_id == expected.trace.trace_id


def test__equation_recognition_cpn__routes_correlated_failure_trace() -> None:
    net = build_equation_recognition_net(assembly(), processor())
    request = project_equation_recognition_request(net)
    failure = workflow_failure(
        request=request,
        error=EquationRecognitionError("bounded recognition failure"),
    )

    observed = record_equation_recognition_failure(net, failure)

    assert observed == failure
    assert observed.trace.final_equation_ids == (
        request.assembly_artifact.artifact_id,
    )

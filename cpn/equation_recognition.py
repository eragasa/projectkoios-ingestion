"""SNAKES shadow of the vendor-neutral equation-recognition workflow."""

from __future__ import annotations

from projectkoios.ingestion.equations.assembly.result import (
    EquationAssemblyResult,
)
from projectkoios.ingestion.equations.derivation.recognition.failure import (
    EquationRecognitionDerivationFailure,
)
from projectkoios.ingestion.equations.derivation.recognition.result import (
    EquationRecognitionDerivationResult,
)
from projectkoios.ingestion.equations.recognition.artifact import (
    EquationRecognitionArtifact,
)
from projectkoios.ingestion.equations.recognition.processor.identity import (
    EquationRecognitionProcessorIdentity,
)
from projectkoios.ingestion.equations.recognition.request import (
    EquationRecognitionRequest,
)
from snakes.nets import (  # type: ignore[import-untyped]
    Expression,
    PetriNet,
    Place,
    Test,
    Transition,
    Variable,
)
from snakes.typing import Instance  # type: ignore[import-untyped]

from workflow.equation_recognition import (
    plan_equation_recognition,
    record_equation_recognition_derivation,
)

EquationRecognitionFailureToken = EquationRecognitionDerivationFailure


class EquationRecognitionCpnError(RuntimeError):
    """Raised when the bounded equation-recognition net is inconsistent."""


def _recognition_request(
    assembly: EquationAssemblyResult,
    processor: EquationRecognitionProcessorIdentity,
) -> EquationRecognitionRequest:
    return plan_equation_recognition(
        assembly=assembly,
        processor=processor,
    )


def _recognition_derivation(
    request: EquationRecognitionRequest,
    result: EquationRecognitionArtifact,
) -> EquationRecognitionDerivationResult:
    return record_equation_recognition_derivation(
        request=request,
        result=result,
    )


def _net(value: object) -> PetriNet:
    if type(value) is not PetriNet:
        raise TypeError("net must be a SNAKES PetriNet")
    return value


def _fire_exactly_one(net: PetriNet, transition_name: str) -> None:
    transition = net.transition(transition_name)
    modes = transition.modes()
    if len(modes) != 1:
        raise EquationRecognitionCpnError(
            f"CPN transition {transition_name!r} requires exactly one mode"
        )
    transition.fire(modes[0])


def build_equation_recognition_net(
    assembly: EquationAssemblyResult,
    processor: EquationRecognitionProcessorIdentity,
) -> object:
    """Build the bounded net without executing an external effect."""

    if type(assembly) is not EquationAssemblyResult:
        raise TypeError("assembly must be an EquationAssemblyResult")
    if type(processor) is not EquationRecognitionProcessorIdentity:
        raise TypeError(
            "processor must be an EquationRecognitionProcessorIdentity"
        )
    net = PetriNet("equation-recognition")
    net.globals["recognition_request"] = _recognition_request
    net.globals["recognition_derivation"] = _recognition_derivation
    net.add_place(
        Place(
            "assembly_ready",
            [assembly],
            Instance(EquationAssemblyResult),
        )
    )
    net.add_place(
        Place(
            "processor_ready",
            [processor],
            Instance(EquationRecognitionProcessorIdentity),
        )
    )
    net.add_place(
        Place(
            "recognition_requested",
            check=Instance(EquationRecognitionRequest),
        )
    )
    net.add_place(
        Place("external_results", check=Instance(EquationRecognitionArtifact))
    )
    net.add_place(
        Place(
            "external_failures",
            check=Instance(EquationRecognitionDerivationFailure),
        )
    )
    net.add_place(
        Place(
            "recognition_complete",
            check=Instance(EquationRecognitionDerivationResult),
        )
    )
    net.add_place(
        Place(
            "recognition_failed",
            check=Instance(EquationRecognitionDerivationFailure),
        )
    )

    net.add_transition(Transition("request_recognition"))
    net.add_input("assembly_ready", "request_recognition", Variable("assembly"))
    net.add_input(
        "processor_ready",
        "request_recognition",
        Test(Variable("processor")),
    )
    net.add_output(
        "recognition_requested",
        "request_recognition",
        Expression("recognition_request(assembly, processor)"),
    )

    net.add_transition(
        Transition(
            "record_recognition_result",
            Expression("request.request_id == result.request_id"),
        )
    )
    net.add_input(
        "recognition_requested",
        "record_recognition_result",
        Variable("request"),
    )
    net.add_input(
        "external_results",
        "record_recognition_result",
        Variable("result"),
    )
    net.add_output(
        "recognition_complete",
        "record_recognition_result",
        Expression("recognition_derivation(request, result)"),
    )

    net.add_transition(
        Transition(
            "record_recognition_failure",
            Expression("request.request_id == failure.request.request_id"),
        )
    )
    net.add_input(
        "recognition_requested",
        "record_recognition_failure",
        Variable("request"),
    )
    net.add_input(
        "external_failures",
        "record_recognition_failure",
        Variable("failure"),
    )
    net.add_output(
        "recognition_failed",
        "record_recognition_failure",
        Expression("failure"),
    )
    return net


def project_equation_recognition_request(
    net: object,
) -> EquationRecognitionRequest:
    """Fire the pure request projection and return its typed token."""

    actual = _net(net)
    _fire_exactly_one(actual, "request_recognition")
    requests = tuple(actual.place("recognition_requested"))
    if (
        len(requests) != 1
        or type(requests[0]) is not EquationRecognitionRequest
    ):
        raise EquationRecognitionCpnError(
            "CPN did not produce one recognition request"
        )
    return requests[0]


def record_equation_recognition_result(
    net: object,
    result: EquationRecognitionArtifact,
) -> EquationRecognitionDerivationResult:
    """Correlate one externally supplied result and derive its trace."""

    if type(result) is not EquationRecognitionArtifact:
        raise TypeError("result must be an EquationRecognitionArtifact")
    actual = _net(net)
    actual.place("external_results").add(result)
    _fire_exactly_one(actual, "record_recognition_result")
    completed = tuple(actual.place("recognition_complete"))
    if (
        len(completed) != 1
        or type(completed[0]) is not EquationRecognitionDerivationResult
        or completed[0].recognition != result
    ):
        raise EquationRecognitionCpnError(
            "CPN did not correlate the recognition result"
        )
    return completed[0]


def record_equation_recognition_failure(
    net: object,
    failure: EquationRecognitionDerivationFailure,
) -> EquationRecognitionDerivationFailure:
    """Correlate one workflow-derived exceptional failure through the net."""

    if type(failure) is not EquationRecognitionDerivationFailure:
        raise TypeError(
            "failure must be an EquationRecognitionDerivationFailure"
        )
    actual = _net(net)
    actual.place("external_failures").add(failure)
    _fire_exactly_one(actual, "record_recognition_failure")
    if failure not in actual.place("recognition_failed"):
        raise EquationRecognitionCpnError(
            "CPN did not route the recognition failure"
        )
    return failure

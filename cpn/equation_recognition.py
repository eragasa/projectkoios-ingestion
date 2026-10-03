"""SNAKES shadow of the vendor-neutral equation-recognition workflow."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.equation_enrichment import (
    EquationAssemblyArtifact,
    EquationRecognitionArtifact,
    EquationRecognitionProcessorIdentity,
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

from workflow.equation_recognition import plan_equation_recognition


class EquationRecognitionCpnError(RuntimeError):
    """Raised when the bounded equation-recognition net is inconsistent."""


@dataclass(frozen=True, slots=True)
class EquationRecognitionFailureToken:
    """CPN token routed after an equation-recognition exception."""

    request_id: str
    message: str

    def __post_init__(self) -> None:
        if not self.request_id or not self.message:
            raise ValueError("recognition failure token is incomplete")
        if len(self.message) > 1_024:
            raise ValueError("recognition failure token exceeds its bound")


def _recognition_request(
    assembly: EquationAssemblyArtifact,
    processor: EquationRecognitionProcessorIdentity,
) -> EquationRecognitionRequest:
    return plan_equation_recognition(
        assembly=assembly,
        processor=processor,
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
    assembly: EquationAssemblyArtifact,
    processor: EquationRecognitionProcessorIdentity,
) -> object:
    """Build the bounded net without executing an external effect."""

    if type(assembly) is not EquationAssemblyArtifact:
        raise TypeError("assembly must be an EquationAssemblyArtifact")
    if type(processor) is not EquationRecognitionProcessorIdentity:
        raise TypeError(
            "processor must be an EquationRecognitionProcessorIdentity"
        )
    net = PetriNet("equation-recognition")
    net.globals["recognition_request"] = _recognition_request
    net.add_place(
        Place(
            "assembly_ready",
            [assembly],
            Instance(EquationAssemblyArtifact),
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
            check=Instance(EquationRecognitionFailureToken),
        )
    )
    net.add_place(
        Place(
            "recognition_complete",
            check=Instance(EquationRecognitionArtifact),
        )
    )
    net.add_place(
        Place(
            "recognition_failed",
            check=Instance(EquationRecognitionFailureToken),
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
        Expression("result"),
    )

    net.add_transition(
        Transition(
            "record_recognition_failure",
            Expression("request.request_id == failure.request_id"),
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
) -> EquationRecognitionArtifact:
    """Correlate one externally supplied result through the net."""

    if type(result) is not EquationRecognitionArtifact:
        raise TypeError("result must be an EquationRecognitionArtifact")
    actual = _net(net)
    actual.place("external_results").add(result)
    _fire_exactly_one(actual, "record_recognition_result")
    completed = tuple(actual.place("recognition_complete"))
    if completed != (result,):
        raise EquationRecognitionCpnError(
            "CPN did not correlate the recognition result"
        )
    return result


def record_equation_recognition_failure(
    net: object,
    failure: EquationRecognitionFailureToken,
) -> EquationRecognitionFailureToken:
    """Correlate one workflow-supplied failure token through the net."""

    if type(failure) is not EquationRecognitionFailureToken:
        raise TypeError("failure must be an EquationRecognitionFailureToken")
    actual = _net(net)
    actual.place("external_failures").add(failure)
    _fire_exactly_one(actual, "record_recognition_failure")
    if failure not in actual.place("recognition_failed"):
        raise EquationRecognitionCpnError(
            "CPN did not route the recognition failure"
        )
    return failure

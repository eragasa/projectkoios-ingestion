"""Compact durable equation-recognition derivation record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.equations.derivation.recognition.result import (
    EquationRecognitionDerivationResult,
)
from projectkoios.ingestion.equations.derivation.status import (
    EquationDerivationTransitionStatus,
)
from projectkoios.ingestion.equations.derivation.trace import (
    EquationDerivationTrace,
)
from projectkoios.ingestion.equations.derivation.transition import (
    EquationDerivationTransition,
)
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class EquationRecognitionDerivationRecord(AbstractImmutableDataObject):
    """Compact correlation identities and complete representation trace."""

    CONTRACT_NAME: ClassVar[str] = "equation-recognition-derivation-record"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    record_id: str
    request_id: str
    recognition_artifact_id: str
    trace: EquationDerivationTrace

    @classmethod
    def create(
        cls,
        result: EquationRecognitionDerivationResult,
    ) -> EquationRecognitionDerivationRecord:
        if type(result) is not EquationRecognitionDerivationResult:
            raise TypeError(
                "result must be an EquationRecognitionDerivationResult"
            )
        return cls(
            record_id=stable_id(
                "equation-recognition-derivation-record",
                cls.CONTRACT_VERSION,
                result.request.request_id,
                result.recognition.artifact_id,
                result.trace.trace_id,
            ),
            request_id=result.request.request_id,
            recognition_artifact_id=result.recognition.artifact_id,
            trace=result.trace,
        )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> EquationRecognitionDerivationRecord:
        """Rehydrate and validate an exact serialized derivation record."""
        record = _exact_object(
            value,
            {
                "record_id",
                "request_id",
                "recognition_artifact_id",
                "trace",
            },
            "recognition derivation record",
        )
        trace_value = _exact_object(
            record["trace"],
            {
                "root_equation_ids",
                "transitions",
                "trace_id",
                "final_equation_ids",
            },
            "equation derivation trace",
        )
        transition_values = trace_value["transitions"]
        if not isinstance(transition_values, list):
            raise TypeError("equation derivation transitions must be a list")
        transitions = tuple(
            _transition_from_dict(transition_value)
            for transition_value in transition_values
        )
        trace = EquationDerivationTrace(
            root_equation_ids=_string_tuple(
                trace_value["root_equation_ids"],
                "equation derivation root IDs",
            ),
            transitions=transitions,
        )
        if trace.trace_id != trace_value["trace_id"] or (
            trace.final_equation_ids
            != _string_tuple(
                trace_value["final_equation_ids"],
                "equation derivation final IDs",
            )
        ):
            raise ValueError(
                "serialized equation derivation trace is inconsistent"
            )
        return cls(
            record_id=_string(record["record_id"], "derivation record ID"),
            request_id=_string(record["request_id"], "derivation request ID"),
            recognition_artifact_id=_string(
                record["recognition_artifact_id"],
                "derivation recognition artifact ID",
            ),
            trace=trace,
        )

    def __post_init__(self) -> None:
        if type(self.trace) is not EquationDerivationTrace:
            raise TypeError("trace must be an EquationDerivationTrace")
        for name, value in (
            ("request ID", self.request_id),
            ("recognition artifact ID", self.recognition_artifact_id),
        ):
            if type(value) is not str or not value or value != value.strip():
                raise ValueError(f"recognition derivation {name} is invalid")
        expected = stable_id(
            "equation-recognition-derivation-record",
            self.CONTRACT_VERSION,
            self.request_id,
            self.recognition_artifact_id,
            self.trace.trace_id,
        )
        if self.record_id != expected:
            raise ValueError("recognition derivation record ID is inconsistent")


def _transition_from_dict(value: object) -> EquationDerivationTransition:
    serialized = _exact_object(
        value,
        {
            "sequence",
            "operation_name",
            "operation_version",
            "input_ids",
            "output_ids",
            "request_id",
            "result_id",
            "processor_identity",
            "configuration_identity",
            "status",
            "warning_codes",
            "failure_type",
            "failure_message",
            "transition_id",
        },
        "equation derivation transition",
    )
    status_value = _string(serialized["status"], "derivation status")
    try:
        status = EquationDerivationTransitionStatus(status_value)
    except ValueError as error:
        raise ValueError("serialized derivation status is invalid") from error
    transition = EquationDerivationTransition(
        sequence=_integer(
            serialized["sequence"],
            "derivation transition sequence",
        ),
        operation_name=_string(
            serialized["operation_name"],
            "derivation operation name",
        ),
        operation_version=_string(
            serialized["operation_version"],
            "derivation operation version",
        ),
        input_ids=_string_tuple(
            serialized["input_ids"],
            "derivation input IDs",
        ),
        output_ids=_string_tuple(
            serialized["output_ids"],
            "derivation output IDs",
        ),
        request_id=_string(serialized["request_id"], "derivation request ID"),
        result_id=_optional_string(
            serialized["result_id"],
            "derivation result ID",
        ),
        processor_identity=_string(
            serialized["processor_identity"],
            "derivation processor identity",
        ),
        configuration_identity=_string(
            serialized["configuration_identity"],
            "derivation configuration identity",
        ),
        status=status,
        warning_codes=_string_tuple(
            serialized["warning_codes"],
            "derivation warning codes",
        ),
        failure_type=_optional_string(
            serialized["failure_type"],
            "derivation failure type",
        ),
        failure_message=_optional_string(
            serialized["failure_message"],
            "derivation failure message",
        ),
    )
    if transition.transition_id != serialized["transition_id"]:
        raise ValueError("serialized derivation transition ID is inconsistent")
    return transition


def _exact_object(
    value: object,
    expected_keys: set[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ValueError(f"serialized {label} has an invalid shape")
    if any(type(key) is not str for key in value):
        raise TypeError(f"serialized {label} keys must be strings")
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str:
        raise TypeError(f"serialized {label} must be a string")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"serialized {label} must be an integer")
    return value


def _optional_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _string(value, label)


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        type(item) is not str for item in value
    ):
        raise TypeError(f"serialized {label} must be a string list")
    return tuple(value)

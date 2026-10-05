"""One exact equation-representation derivation transition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.equations.derivation.status import (
    EquationDerivationTransitionStatus,
)
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class EquationDerivationTransition(AbstractImmutableDataObject):
    """Ordered success or exceptional failure in an equation derivation."""

    CONTRACT_NAME: ClassVar[str] = "equation-derivation-transition"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAX_IDENTITIES: ClassVar[int] = 256
    MAX_ID_CHARACTERS: ClassVar[int] = 4_096
    MAX_WARNING_CODES: ClassVar[int] = 256
    MAX_FAILURE_CHARACTERS: ClassVar[int] = 1_024

    sequence: int
    operation_name: str
    operation_version: str
    input_ids: tuple[str, ...]
    output_ids: tuple[str, ...]
    request_id: str
    result_id: str | None
    processor_identity: str
    configuration_identity: str
    status: EquationDerivationTransitionStatus
    warning_codes: tuple[str, ...] = ()
    failure_type: str | None = None
    failure_message: str | None = None
    transition_id: str = field(init=False)

    @classmethod
    def succeeded(
        cls,
        *,
        sequence: int,
        operation_name: str,
        operation_version: str,
        input_ids: tuple[str, ...],
        output_ids: tuple[str, ...],
        request_id: str,
        result_id: str,
        processor_identity: str,
        configuration_identity: str,
        warning_codes: tuple[str, ...] = (),
    ) -> EquationDerivationTransition:
        return cls(
            sequence=sequence,
            operation_name=operation_name,
            operation_version=operation_version,
            input_ids=input_ids,
            output_ids=output_ids,
            request_id=request_id,
            result_id=result_id,
            processor_identity=processor_identity,
            configuration_identity=configuration_identity,
            status=EquationDerivationTransitionStatus.SUCCEEDED,
            warning_codes=warning_codes,
        )

    @classmethod
    def failed(
        cls,
        *,
        sequence: int,
        operation_name: str,
        operation_version: str,
        input_ids: tuple[str, ...],
        request_id: str,
        processor_identity: str,
        configuration_identity: str,
        failure_type: str,
        failure_message: str,
        warning_codes: tuple[str, ...] = (),
    ) -> EquationDerivationTransition:
        return cls(
            sequence=sequence,
            operation_name=operation_name,
            operation_version=operation_version,
            input_ids=input_ids,
            output_ids=(),
            request_id=request_id,
            result_id=None,
            processor_identity=processor_identity,
            configuration_identity=configuration_identity,
            status=EquationDerivationTransitionStatus.FAILED,
            warning_codes=warning_codes,
            failure_type=failure_type,
            failure_message=failure_message,
        )

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(
            self.sequence, int
        ):
            raise TypeError("derivation transition sequence must be an integer")
        if self.sequence < 1:
            raise ValueError("derivation transition sequence must be positive")
        self._validate_identity(self.operation_name, "operation name")
        self._validate_identity(self.operation_version, "operation version")
        self._validate_ids(self.input_ids, "input IDs", allow_empty=False)
        self._validate_ids(
            self.output_ids,
            "output IDs",
            allow_empty=(
                self.status is EquationDerivationTransitionStatus.FAILED
            ),
        )
        self._validate_identity(self.request_id, "request ID")
        self._validate_identity(self.processor_identity, "processor identity")
        self._validate_identity(
            self.configuration_identity,
            "configuration identity",
        )
        self._validate_ids(
            self.warning_codes,
            "warning codes",
            allow_empty=True,
            maximum=self.MAX_WARNING_CODES,
        )
        if self.status is EquationDerivationTransitionStatus.SUCCEEDED:
            if self.result_id is None:
                raise ValueError("successful derivation requires a result ID")
            self._validate_identity(self.result_id, "result ID")
            if (
                self.failure_type is not None
                or self.failure_message is not None
            ):
                raise ValueError(
                    "successful derivation cannot contain failure evidence"
                )
        elif self.status is EquationDerivationTransitionStatus.FAILED:
            if self.result_id is not None or self.output_ids:
                raise ValueError(
                    "failed derivation cannot contain outputs or a result ID"
                )
            if self.failure_type is None or self.failure_message is None:
                raise ValueError("failed derivation requires failure evidence")
            self._validate_identity(self.failure_type, "failure type")
            if (
                not self.failure_message.strip()
                or len(self.failure_message) > self.MAX_FAILURE_CHARACTERS
            ):
                raise ValueError("derivation failure message is invalid")
        else:
            raise TypeError("derivation transition status is invalid")
        object.__setattr__(
            self,
            "transition_id",
            stable_id(
                "equation-derivation-transition",
                self.CONTRACT_VERSION,
                self.sequence,
                self.operation_name,
                self.operation_version,
                self.input_ids,
                self.output_ids,
                self.request_id,
                self.result_id,
                self.processor_identity,
                self.configuration_identity,
                self.status,
                self.warning_codes,
                self.failure_type,
                self.failure_message,
            ),
        )

    @classmethod
    def _validate_identity(cls, value: str, label: str) -> None:
        if (
            type(value) is not str
            or not value
            or value != value.strip()
            or len(value) > cls.MAX_ID_CHARACTERS
        ):
            raise ValueError(f"derivation transition {label} is invalid")

    @classmethod
    def _validate_ids(
        cls,
        values: tuple[str, ...],
        label: str,
        *,
        allow_empty: bool,
        maximum: int = MAX_IDENTITIES,
    ) -> None:
        if type(values) is not tuple:
            raise TypeError(f"derivation transition {label} must be a tuple")
        if (
            (not allow_empty and not values)
            or len(values) > maximum
            or len(values) != len(set(values))
        ):
            raise ValueError(f"derivation transition {label} are invalid")
        for value in values:
            cls._validate_identity(value, label)

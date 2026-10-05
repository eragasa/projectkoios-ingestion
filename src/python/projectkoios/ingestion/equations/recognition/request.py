"""Vendor-neutral equation-recognition request."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.equations.assembly.result import (
    EquationAssemblyResult,
)
from projectkoios.ingestion.equations.recognition.identity import (
    EQUATION_RECOGNITION_CONTRACT_VERSION,
    equation_recognition_request_id,
)
from projectkoios.ingestion.equations.recognition.processor.identity import (
    EquationRecognitionProcessorIdentity,
)


@dataclass(frozen=True)
class EquationRecognitionRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Request one recognition effect for an exact assembly and processor."""

    CONTRACT_NAME: ClassVar[str] = "equation-recognition-request"
    CONTRACT_VERSION: ClassVar[str] = EQUATION_RECOGNITION_CONTRACT_VERSION

    request_id: str
    assembly_artifact: EquationAssemblyResult
    processor_identity: EquationRecognitionProcessorIdentity

    @classmethod
    def create(
        cls,
        *,
        assembly_artifact: EquationAssemblyResult,
        processor_identity: EquationRecognitionProcessorIdentity,
    ) -> EquationRecognitionRequest:
        return cls(
            request_id=equation_recognition_request_id(
                assembly_artifact.artifact_id,
                processor_identity.identity_digest,
            ),
            assembly_artifact=assembly_artifact,
            processor_identity=processor_identity,
        )

    def __post_init__(self) -> None:
        if type(self.assembly_artifact) is not EquationAssemblyResult:
            raise TypeError(
                "assembly_artifact must be an EquationAssemblyResult"
            )
        if (
            type(self.processor_identity)
            is not EquationRecognitionProcessorIdentity
        ):
            raise TypeError(
                "processor_identity must be an "
                "EquationRecognitionProcessorIdentity"
            )
        expected = equation_recognition_request_id(
            self.assembly_artifact.artifact_id,
            self.processor_identity.identity_digest,
        )
        if self.request_id != expected:
            raise ValueError("equation recognition request ID is inconsistent")

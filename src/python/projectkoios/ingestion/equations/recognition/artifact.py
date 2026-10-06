"""Vendor-neutral equation-recognition artifact."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.equations.recognition.identity import (
    EQUATION_RECOGNITION_CONTRACT_VERSION,
    equation_recognition_request_id,
)
from projectkoios.ingestion.equations.recognition.processor.identity import (
    EquationRecognitionProcessorIdentity,
)
from projectkoios.ingestion.equations.recognition.proposal import (
    EquationRecognitionProposal,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.sha256.hash import SHA256Hash

_MAX_DIAGNOSTIC_BYTES = 4_000_000


@dataclass(frozen=True)
class EquationRecognitionArtifact(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Result token produced for one exact recognition request."""

    CONTRACT_NAME: ClassVar[str] = "equation-recognition-artifact"
    CONTRACT_VERSION: ClassVar[str] = EQUATION_RECOGNITION_CONTRACT_VERSION

    artifact_id: str
    assembly_artifact_id: str
    processor_identity: EquationRecognitionProcessorIdentity
    proposals: tuple[EquationRecognitionProposal, ...]
    invocation_exit_code: int
    diagnostic_byte_size: int
    diagnostic_sha256: str
    contract_version: str = EQUATION_RECOGNITION_CONTRACT_VERSION

    @property
    def request_id(self) -> str:
        """Return the request identity bound by this result token."""

        return equation_recognition_request_id(
            self.assembly_artifact_id,
            self.processor_identity.identity_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_RECOGNITION_CONTRACT_VERSION:
            raise ValueError(
                "unsupported equation recognition artifact version"
            )
        if (
            self.diagnostic_byte_size < 0
            or self.diagnostic_byte_size > _MAX_DIAGNOSTIC_BYTES
        ):
            raise ValueError("recognition diagnostic size is out of bounds")
        if not SHA256Hash.is_canonical(self.diagnostic_sha256):
            raise ValueError("recognition diagnostic hash must be SHA-256")
        if type(self.proposals) is not tuple or any(
            type(proposal) is not EquationRecognitionProposal
            for proposal in self.proposals
        ):
            raise TypeError("recognition proposals must be a typed tuple")
        proposal_ids = tuple(item.proposal_id for item in self.proposals)
        assembly_ids = tuple(item.assembly_id for item in self.proposals)
        if len(proposal_ids) != len(set(proposal_ids)):
            raise ValueError("recognition proposal IDs must be unique")
        if len(assembly_ids) != len(set(assembly_ids)):
            raise ValueError("recognition proposal assemblies must be unique")
        expected = stable_id(
            "equation-recognition-artifact",
            EQUATION_RECOGNITION_CONTRACT_VERSION,
            self.assembly_artifact_id,
            self.processor_identity.identity_digest,
            proposal_ids,
            self.invocation_exit_code,
            self.diagnostic_byte_size,
            self.diagnostic_sha256,
        )
        if self.artifact_id != expected:
            raise ValueError("equation recognition artifact ID is inconsistent")

"""Result of extraction projection and materialization pipeline execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.base.pipeline.result import PipelineResult
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.materialization.evidence import (
    ExtractionProjectionMaterializationEvidence,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionPipelineResult(
    AbstractImmutableDataObject,
    PipelineResult,
):
    """Retain stage identities and final materialization evidence."""

    CONTRACT_NAME: ClassVar[str] = "extraction-projection-pipeline-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    request_id: str
    idempotency_key: str
    projection_result_id: str
    materialization_result_id: str
    evidence: ExtractionProjectionMaterializationEvidence
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request_id: str,
        idempotency_key: str,
        projection_result_id: str,
        materialization_result_id: str,
        evidence: ExtractionProjectionMaterializationEvidence,
    ) -> ExtractionProjectionPipelineResult:
        """Create one result without retaining the complete projected graph."""
        parts = (
            request_id,
            idempotency_key,
            projection_result_id,
            materialization_result_id,
            evidence.evidence_id,
        )
        return cls(
            result_id=stable_id(
                "extraction-projection-pipeline-result",
                cls.CONTRACT_VERSION,
                parts,
            ),
            request_id=request_id,
            idempotency_key=idempotency_key,
            projection_result_id=projection_result_id,
            materialization_result_id=materialization_result_id,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported extraction pipeline result")
        if (
            type(self.evidence)
            is not ExtractionProjectionMaterializationEvidence
        ):
            raise TypeError("pipeline evidence has the wrong contract")
        parts = (
            self.request_id,
            self.idempotency_key,
            self.projection_result_id,
            self.materialization_result_id,
            self.evidence.evidence_id,
        )
        if any(type(value) is not str or not value for value in parts[:-1]):
            raise ValueError("pipeline result identity is incomplete")
        expected = stable_id(
            "extraction-projection-pipeline-result",
            self.CONTRACT_VERSION,
            parts,
        )
        if self.result_id != expected:
            raise ValueError("pipeline result ID is inconsistent")

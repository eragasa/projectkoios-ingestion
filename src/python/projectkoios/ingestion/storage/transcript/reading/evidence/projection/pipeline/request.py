"""Request for reading-evidence projection and materialization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.target import (  # noqa: E501
    ReadingEvidenceMaterializationTarget,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.pipeline.configuration import (  # noqa: E501
    ReadingEvidenceProjectionPipelineConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.source import (  # noqa: E501
    ReadingEvidenceStorageProjectionSource,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceProjectionPipelineRequest(
    AbstractImmutableDataObject,
    ConfigurableDataObjectActionRequest[
        ReadingEvidenceProjectionPipelineConfiguration
    ],
):
    """Bind one canonical source, target, configuration, and authority."""

    CONTRACT_NAME: ClassVar[str] = (
        "reading-evidence-projection-pipeline-request"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    idempotency_key: str
    source: ReadingEvidenceStorageProjectionSource
    target: ReadingEvidenceMaterializationTarget
    configuration: ReadingEvidenceProjectionPipelineConfiguration
    authority_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source: ReadingEvidenceStorageProjectionSource,
        target: ReadingEvidenceMaterializationTarget,
        configuration: ReadingEvidenceProjectionPipelineConfiguration,
        authority_id: str,
    ) -> ReadingEvidenceProjectionPipelineRequest:
        """Create one authority-bound request with a stable replay key."""
        values = (
            source.evidence_id,
            source.canonical_sha256,
            target.target_id,
            configuration.configuration_id,
        )
        idempotency_key = stable_id(
            "reading-evidence-projection-pipeline-idempotency",
            cls.CONTRACT_VERSION,
            values,
        )
        return cls(
            request_id=stable_id(
                "reading-evidence-projection-pipeline-request",
                cls.CONTRACT_VERSION,
                idempotency_key,
                authority_id,
            ),
            idempotency_key=idempotency_key,
            source=source,
            target=target,
            configuration=configuration,
            authority_id=authority_id,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported reading-evidence pipeline request")
        if type(self.source) is not ReadingEvidenceStorageProjectionSource:
            raise TypeError("pipeline source has the wrong contract")
        if type(self.target) is not ReadingEvidenceMaterializationTarget:
            raise TypeError("pipeline target has the wrong contract")
        if (
            type(self.configuration)
            is not ReadingEvidenceProjectionPipelineConfiguration
        ):
            raise TypeError("pipeline configuration has the wrong contract")
        if type(self.authority_id) is not str or not self.authority_id:
            raise ValueError("pipeline authority must be non-empty")
        values = (
            self.source.evidence_id,
            self.source.canonical_sha256,
            self.target.target_id,
            self.configuration.configuration_id,
        )
        expected_key = stable_id(
            "reading-evidence-projection-pipeline-idempotency",
            self.CONTRACT_VERSION,
            values,
        )
        if self.idempotency_key != expected_key:
            raise ValueError("pipeline idempotency key is inconsistent")
        expected_request = stable_id(
            "reading-evidence-projection-pipeline-request",
            self.CONTRACT_VERSION,
            expected_key,
            self.authority_id,
        )
        if self.request_id != expected_request:
            raise ValueError("pipeline request ID is inconsistent")

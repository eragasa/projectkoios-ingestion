"""Request for extraction projection and materialization pipeline execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.evidence import (
    ExtractionPublicationEvidence,
)
from projectkoios.ingestion.storage.extraction.projection_pipeline.configuration import (  # noqa: E501
    ExtractionProjectionPipelineConfiguration,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionPipelineRequest(
    AbstractImmutableDataObject,
    ConfigurableDataObjectActionRequest[
        ExtractionProjectionPipelineConfiguration
    ],
):
    """Bind complete source evidence, target, configuration, and authority."""

    CONTRACT_NAME: ClassVar[str] = "extraction-projection-pipeline-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    idempotency_key: str
    source: ExtractionPublicationEvidence
    target: ExtractionProjectionTargetIdentity
    configuration: ExtractionProjectionPipelineConfiguration
    authority_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source: ExtractionPublicationEvidence,
        target: ExtractionProjectionTargetIdentity,
        configuration: ExtractionProjectionPipelineConfiguration,
        authority_id: str,
    ) -> ExtractionProjectionPipelineRequest:
        """Create an authority-bound request and neutral replay key."""
        values = (
            source.evidence_id,
            target.target_id,
            configuration.configuration_id,
        )
        idempotency_key = stable_id(
            "extraction-projection-pipeline-idempotency",
            cls.CONTRACT_VERSION,
            values,
        )
        return cls(
            request_id=stable_id(
                "extraction-projection-pipeline-request",
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
            raise ValueError("unsupported extraction pipeline request")
        if type(self.source) is not ExtractionPublicationEvidence:
            raise TypeError("pipeline source has the wrong contract")
        if type(self.target) is not ExtractionProjectionTargetIdentity:
            raise TypeError("pipeline target has the wrong contract")
        if (
            type(self.configuration)
            is not ExtractionProjectionPipelineConfiguration
        ):
            raise TypeError("pipeline configuration has the wrong contract")
        if type(self.authority_id) is not str or not self.authority_id:
            raise ValueError("pipeline authority must be non-empty")
        values = (
            self.source.evidence_id,
            self.target.target_id,
            self.configuration.configuration_id,
        )
        expected_key = stable_id(
            "extraction-projection-pipeline-idempotency",
            self.CONTRACT_VERSION,
            values,
        )
        if self.idempotency_key != expected_key:
            raise ValueError("pipeline idempotency key is inconsistent")
        expected_request = stable_id(
            "extraction-projection-pipeline-request",
            self.CONTRACT_VERSION,
            expected_key,
            self.authority_id,
        )
        if self.request_id != expected_request:
            raise ValueError("pipeline request ID is inconsistent")

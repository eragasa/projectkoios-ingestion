"""Request for extraction projection index readiness."""

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
from projectkoios.ingestion.storage.extraction.projection.index.readiness.configuration import (  # noqa: E501
    ExtractionProjectionIndexReadinessConfiguration,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionIndexReadinessRequest(
    AbstractImmutableDataObject,
    ConfigurableDataObjectActionRequest[
        ExtractionProjectionIndexReadinessConfiguration
    ],
):
    """Bind one explicit target, index configuration, and authority."""

    CONTRACT_NAME: ClassVar[str] = (
        "extraction-projection-index-readiness-request"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    AUTHORITY_REQUIREMENT: ClassVar[str] = "extraction_projection_index_write"

    request_id: str
    idempotency_key: str
    target: ExtractionProjectionTargetIdentity
    configuration: ExtractionProjectionIndexReadinessConfiguration
    authority_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        target: ExtractionProjectionTargetIdentity,
        configuration: ExtractionProjectionIndexReadinessConfiguration,
        authority_id: str,
    ) -> ExtractionProjectionIndexReadinessRequest:
        """Create an authority-bound request and neutral readiness key."""
        key = stable_id(
            "extraction-projection-index-readiness-idempotency",
            cls.CONTRACT_VERSION,
            target.target_id,
            configuration.configuration_id,
        )
        return cls(
            request_id=stable_id(
                "extraction-projection-index-readiness-request",
                cls.CONTRACT_VERSION,
                key,
                authority_id,
            ),
            idempotency_key=key,
            target=target,
            configuration=configuration,
            authority_id=authority_id,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported index-readiness request")
        if type(self.target) is not ExtractionProjectionTargetIdentity:
            raise TypeError("index-readiness target is invalid")
        if (
            type(self.configuration)
            is not ExtractionProjectionIndexReadinessConfiguration
        ):
            raise TypeError("index-readiness configuration is invalid")
        if (
            type(self.authority_id) is not str
            or not self.authority_id
            or len(self.authority_id) > 4_096
        ):
            raise ValueError("index-readiness authority is invalid")
        if self.target.schema_id != self.configuration.schema_id:
            raise ValueError("index-readiness schema identities differ")
        key = stable_id(
            "extraction-projection-index-readiness-idempotency",
            self.CONTRACT_VERSION,
            self.target.target_id,
            self.configuration.configuration_id,
        )
        if self.idempotency_key != key:
            raise ValueError("index-readiness idempotency is inconsistent")
        expected = stable_id(
            "extraction-projection-index-readiness-request",
            self.CONTRACT_VERSION,
            key,
            self.authority_id,
        )
        if self.request_id != expected:
            raise ValueError("index-readiness request ID is inconsistent")

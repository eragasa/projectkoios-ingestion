"""Complete configuration for reading-evidence projection materialization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.configuration import (  # noqa: E501
    ReadingEvidenceMaterializationConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.configuration import (  # noqa: E501
    ReadingEvidenceStorageProjectionConfiguration,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceProjectionPipelineConfiguration(
    AbstractActionConfiguration
):
    """Bind pure storage projection and physical materialization choices."""

    CONTRACT_NAME: ClassVar[str] = (
        "reading-evidence-projection-pipeline-configuration"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    configuration_id: str
    projection_configuration: ReadingEvidenceStorageProjectionConfiguration
    materialization_configuration: ReadingEvidenceMaterializationConfiguration
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        projection_configuration: ReadingEvidenceStorageProjectionConfiguration,
        materialization_configuration: (
            ReadingEvidenceMaterializationConfiguration
        ),
    ) -> ReadingEvidenceProjectionPipelineConfiguration:
        """Create one exact two-stage pipeline configuration."""
        return cls(
            configuration_id=stable_id(
                "reading-evidence-projection-pipeline-configuration",
                cls.CONTRACT_VERSION,
                projection_configuration.configuration_id,
                materialization_configuration.configuration_id,
            ),
            projection_configuration=projection_configuration,
            materialization_configuration=materialization_configuration,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported reading-evidence pipeline configuration"
            )
        if (
            type(self.projection_configuration)
            is not ReadingEvidenceStorageProjectionConfiguration
        ):
            raise TypeError("projection configuration has the wrong contract")
        if (
            type(self.materialization_configuration)
            is not ReadingEvidenceMaterializationConfiguration
        ):
            raise TypeError(
                "materialization configuration has the wrong contract"
            )
        if (
            self.projection_configuration.schema_version
            != self.materialization_configuration.schema_version
        ):
            raise ValueError("pipeline stage schemas differ")
        expected = stable_id(
            "reading-evidence-projection-pipeline-configuration",
            self.CONTRACT_VERSION,
            self.projection_configuration.configuration_id,
            self.materialization_configuration.configuration_id,
        )
        if self.configuration_id != expected:
            raise ValueError(
                "reading-evidence pipeline configuration ID differs"
            )

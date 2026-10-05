"""Complete configuration for extraction projection materialization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.materialization.configuration import (  # noqa: E501
    ExtractionProjectionMaterializationConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.configuration import (
    ExtractionProjectionConfiguration,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionPipelineConfiguration(AbstractActionConfiguration):
    """Bind pure projection and effectful materialization configurations."""

    CONTRACT_NAME: ClassVar[str] = (
        "extraction-projection-pipeline-configuration"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    configuration_id: str
    projection_configuration: ExtractionProjectionConfiguration
    materialization_configuration: (
        ExtractionProjectionMaterializationConfiguration
    )
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        projection_configuration: ExtractionProjectionConfiguration,
        materialization_configuration: (
            ExtractionProjectionMaterializationConfiguration
        ),
    ) -> ExtractionProjectionPipelineConfiguration:
        """Create configuration from the two complete stage configurations."""
        return cls(
            configuration_id=stable_id(
                "extraction-projection-pipeline-configuration",
                cls.CONTRACT_VERSION,
                projection_configuration.configuration_id,
                materialization_configuration.configuration_id,
            ),
            projection_configuration=projection_configuration,
            materialization_configuration=materialization_configuration,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported extraction pipeline configuration")
        if (
            type(self.projection_configuration)
            is not ExtractionProjectionConfiguration
        ):
            raise TypeError("projection configuration has the wrong contract")
        if (
            type(self.materialization_configuration)
            is not ExtractionProjectionMaterializationConfiguration
        ):
            raise TypeError(
                "materialization configuration has the wrong contract"
            )
        expected = stable_id(
            "extraction-projection-pipeline-configuration",
            self.CONTRACT_VERSION,
            self.projection_configuration.configuration_id,
            self.materialization_configuration.configuration_id,
        )
        if self.configuration_id != expected:
            raise ValueError("extraction pipeline configuration ID differs")

"""Typed extraction publication projection/materialization pipeline."""

from __future__ import annotations

from projectkoios.ingestion.base.materializer.request import (
    MaterializationRequest,
)
from projectkoios.ingestion.base.pipeline.identity import PipelineIdentity
from projectkoios.ingestion.base.pipeline.pipeline import Pipeline
from projectkoios.ingestion.base.projector.request import ProjectionRequest
from projectkoios.ingestion.storage.extraction.materialization.materializer import (  # noqa: E501
    AbstractExtractionProjectionMaterializer,
)
from projectkoios.ingestion.storage.extraction.projection.projector import (
    ExtractionProjectionProjector,
)
from projectkoios.ingestion.storage.extraction.projection_pipeline.configuration import (  # noqa: E501
    ExtractionProjectionPipelineConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection_pipeline.request import (  # noqa: E501
    ExtractionProjectionPipelineRequest,
)
from projectkoios.ingestion.storage.extraction.projection_pipeline.result import (  # noqa: E501
    ExtractionProjectionPipelineResult,
)


class ExtractionProjectionMaterializationPipeline(
    Pipeline[
        ExtractionProjectionPipelineConfiguration,
        ExtractionProjectionPipelineRequest,
        ExtractionProjectionPipelineResult,
    ]
):
    """Compose pure extraction projection with effectful materialization."""

    __slots__ = ("materializer", "identity")

    has_external_effects = True
    request_type = ExtractionProjectionPipelineRequest
    configuration_type = ExtractionProjectionPipelineConfiguration
    result_type = ExtractionProjectionPipelineResult

    def __init__(
        self,
        *,
        materializer: AbstractExtractionProjectionMaterializer,
    ) -> None:
        if not isinstance(
            materializer,
            AbstractExtractionProjectionMaterializer,
        ):
            raise TypeError("materializer has the wrong contract")
        self.materializer = materializer
        self.identity = PipelineIdentity.create(
            name="extraction-projection-materialization-pipeline",
            version="1.0",
            request_contract=ExtractionProjectionPipelineRequest.CONTRACT_NAME,
            configuration_contract=(
                ExtractionProjectionPipelineConfiguration.CONTRACT_NAME
            ),
            result_contract=ExtractionProjectionPipelineResult.CONTRACT_NAME,
            stage_actionizer_ids=(
                ExtractionProjectionProjector.identity.projector_id,
                materializer.identity.materializer_id,
            ),
            has_external_effects=True,
        )

    def execute(
        self,
        *,
        request: ExtractionProjectionPipelineRequest,
        configuration: ExtractionProjectionPipelineConfiguration,
    ) -> ExtractionProjectionPipelineResult:
        """Project one publication and materialize its complete read model."""
        projection_request = ProjectionRequest.create(
            sources=(request.source,),
            configuration=configuration.projection_configuration,
        )
        projection_result = ExtractionProjectionProjector().action(
            request=projection_request
        )
        materialization_request = MaterializationRequest.create(
            projection=projection_result.projection,
            target=request.target,
            configuration=configuration.materialization_configuration,
            authority_id=request.authority_id,
        )
        materialization_result = self.materializer.action(
            request=materialization_request
        )
        return ExtractionProjectionPipelineResult.create(
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            projection_result_id=projection_result.result_id,
            materialization_result_id=materialization_result.result_id,
            evidence=materialization_result.evidence,
        )

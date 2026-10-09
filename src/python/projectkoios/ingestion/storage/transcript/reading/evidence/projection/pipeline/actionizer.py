"""Reading-evidence projection and materialization pipeline."""

from __future__ import annotations

from projectkoios.ingestion.base.materializer.request import (
    MaterializationRequest,
)
from projectkoios.ingestion.base.pipeline.actionizer import Pipeline
from projectkoios.ingestion.base.pipeline.identity import PipelineIdentity
from projectkoios.ingestion.base.projector.request import ProjectionRequest
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.actionizer import (  # noqa: E501
    ReadingEvidenceMaterializer,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.pipeline.configuration import (  # noqa: E501
    ReadingEvidenceProjectionPipelineConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.pipeline.request import (  # noqa: E501
    ReadingEvidenceProjectionPipelineRequest,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.pipeline.result import (  # noqa: E501
    ReadingEvidenceProjectionPipelineResult,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.projector import (  # noqa: E501
    ReadingEvidenceStorageProjector,
)


class ReadingEvidenceProjectionMaterializationPipeline(
    Pipeline[
        ReadingEvidenceProjectionPipelineConfiguration,
        ReadingEvidenceProjectionPipelineRequest,
        ReadingEvidenceProjectionPipelineResult,
    ]
):
    """Compose pure storage projection with effectful materialization."""

    __slots__ = ("materializer", "identity")

    has_external_effects = True
    request_type = ReadingEvidenceProjectionPipelineRequest
    configuration_type = ReadingEvidenceProjectionPipelineConfiguration
    result_type = ReadingEvidenceProjectionPipelineResult

    def __init__(self, *, materializer: ReadingEvidenceMaterializer) -> None:
        if not isinstance(materializer, ReadingEvidenceMaterializer):
            raise TypeError("materializer has the wrong contract")
        self.materializer = materializer
        self.identity = PipelineIdentity.create(
            name="reading-evidence-projection-materialization-pipeline",
            version="1.0",
            request_contract=ReadingEvidenceProjectionPipelineRequest.CONTRACT_NAME,
            configuration_contract=(
                ReadingEvidenceProjectionPipelineConfiguration.CONTRACT_NAME
            ),
            result_contract=ReadingEvidenceProjectionPipelineResult.CONTRACT_NAME,
            stage_actionizer_ids=(
                ReadingEvidenceStorageProjector.identity.projector_id,
                materializer.identity.materializer_id,
            ),
            has_external_effects=True,
        )

    def execute(
        self,
        *,
        request: ReadingEvidenceProjectionPipelineRequest,
        configuration: ReadingEvidenceProjectionPipelineConfiguration,
    ) -> ReadingEvidenceProjectionPipelineResult:
        """Project one canonical result and materialize its read model."""
        projection_request = ProjectionRequest.create(
            sources=(request.source,),
            configuration=configuration.projection_configuration,
        )
        projection_result = ReadingEvidenceStorageProjector().action(
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
        return ReadingEvidenceProjectionPipelineResult.create(
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            projection_result_id=projection_result.result_id,
            materialization_result_id=materialization_result.result_id,
            evidence=materialization_result.evidence,
        )

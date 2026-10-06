from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import mongomock
from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.base.pipeline.actionizer import Pipeline
from projectkoios.ingestion.integrations.disk.extraction.store import (
    DiskExtractionPublicationStore,
)
from projectkoios.ingestion.integrations.mongodb.extraction.materializer import (  # noqa: E501
    MongoExtractionProjectionMaterializer,
)
from projectkoios.ingestion.models import ExtractionResult
from projectkoios.ingestion.storage.extraction.materialization.configuration import (  # noqa: E501
    ExtractionProjectionMaterializationConfiguration,
)
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.configuration import (
    ExtractionProjectionConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.evidence import (
    ExtractionPublicationEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.pipeline.actionizer import (  # noqa: E501
    ExtractionProjectionMaterializationPipeline,
)
from projectkoios.ingestion.storage.extraction.projection.pipeline.configuration import (  # noqa: E501
    ExtractionProjectionPipelineConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.pipeline.request import (  # noqa: E501
    ExtractionProjectionPipelineRequest,
)
from projectkoios.ingestion.storage.extraction.projection.projector import (
    ExtractionProjectionProjector,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)
from pymongo.database import Database


def test__pipeline__inherits_configurable_actionizer() -> None:
    assert issubclass(Pipeline, ConfigurableDataObjectActionizer)


def test__extraction_projection_pipeline__composes_typed_stages(
    extraction_result: ExtractionResult,
    tmp_path: Path,
) -> None:
    journal = DiskExtractionPublicationStore(tmp_path / "journal")
    journal.publish(
        request=ExtractionPublicationRequest.create(
            extraction=extraction_result
        )
    )
    record = journal.records()[0]
    source = ExtractionPublicationEvidence.create(
        record=record,
        payload=journal.payload(record),
    )
    database = cast(
        Database[dict[str, Any]],
        mongomock.MongoClient().pipeline_test,
    )
    target = ExtractionProjectionTargetIdentity.create(
        deployment_id="local-test-mongodb",
        environment="test",
        database_name=database.name,
        schema_id="extraction-read-model-v1",
        projection_slot="extraction-publications",
    )
    materializer = MongoExtractionProjectionMaterializer(
        database=database,
        configured_target=target,
    )
    pipeline = ExtractionProjectionMaterializationPipeline(
        materializer=materializer
    )
    configuration = ExtractionProjectionPipelineConfiguration.create(
        projection_configuration=ExtractionProjectionConfiguration.v1(),
        materialization_configuration=(
            ExtractionProjectionMaterializationConfiguration.mongodb_v1()
        ),
    )
    request = ExtractionProjectionPipelineRequest.create(
        source=source,
        target=target,
        configuration=configuration,
        authority_id="authority:test-extraction-write",
    )

    first = pipeline.action(request=request)
    second = pipeline.action(request=request)

    assert first.request_id == request.request_id
    assert first.evidence.created_document_count == 4
    assert second.evidence.unchanged_document_count == 4
    assert not hasattr(first, "projection")
    assert pipeline.identity.stage_actionizer_ids == (
        ExtractionProjectionProjector.identity.projector_id,
        materializer.identity.materializer_id,
    )

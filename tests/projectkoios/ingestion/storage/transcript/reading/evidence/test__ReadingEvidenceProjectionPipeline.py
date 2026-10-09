"""Fixed reading-evidence projection/materialization pipeline tests."""

from __future__ import annotations

from typing import Any, cast

import mongomock
from projectkoios.ingestion.base.pipeline.actionizer import Pipeline
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.configuration import (  # noqa: E501
    MongoReadingEvidenceConfiguration,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.index.readiness.actionizer import (  # noqa: E501
    MongoReadingEvidenceIndexReadinessActionizer,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.index.readiness.request import (  # noqa: E501
    MongoReadingEvidenceIndexReadinessRequest,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.materialization.actionizer import (  # noqa: E501
    MongoReadingEvidenceMaterializer,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.source.actionizer import (  # noqa: E501
    MongoReadingEvidenceSourceActionizer,
)
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.source.reader import (  # noqa: E501
    MongoReadingEvidenceReadModelReader,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.kind import (  # noqa: E501
    ReadingEvidenceEquivalenceKind,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.request import (  # noqa: E501
    ReadingEvidenceEquivalenceRequest,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.verifier import (  # noqa: E501
    ReadingEvidenceEquivalenceVerifier,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.target import (  # noqa: E501
    ReadingEvidenceMaterializationTarget,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.configuration import (  # noqa: E501
    ReadingEvidenceStorageProjectionConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.pipeline.actionizer import (  # noqa: E501
    ReadingEvidenceProjectionMaterializationPipeline,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.pipeline.configuration import (  # noqa: E501
    ReadingEvidenceProjectionPipelineConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.pipeline.request import (  # noqa: E501
    ReadingEvidenceProjectionPipelineRequest,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.projector import (  # noqa: E501
    ReadingEvidenceStorageProjector,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.source import (  # noqa: E501
    ReadingEvidenceStorageProjectionSource,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.source.verifier import (  # noqa: E501
    ReadingEvidenceReadModelVerifier,
)
from projectkoios.ingestion.transcript.reading.evidence.source.result import (
    ReadingEvidenceSourceResult,
)
from pymongo.database import Database

from tests.projectkoios.ingestion.storage.transcript.reading.evidence.fixture import (  # noqa: E501
    ReadingEvidenceStorageFixture,
)

MongoDocument = dict[str, Any]


def _target(
    *,
    database: Database[MongoDocument],
    configuration: MongoReadingEvidenceConfiguration,
    deployment_id: str,
) -> ReadingEvidenceMaterializationTarget:
    return ReadingEvidenceMaterializationTarget.create(
        deployment_id=deployment_id,
        environment="test",
        store_name=database.name,
        schema_id=configuration.materialization.schema_id,
    )


def _source_result(
    *,
    database: Database[MongoDocument],
    configuration: MongoReadingEvidenceConfiguration,
    target: ReadingEvidenceMaterializationTarget,
    fixture: ReadingEvidenceStorageFixture,
) -> ReadingEvidenceSourceResult:
    MongoReadingEvidenceIndexReadinessActionizer(
        database=database,
        configured_target=target,
    ).action(
        request=MongoReadingEvidenceIndexReadinessRequest(
            target=target,
            configuration=configuration,
            authority_id="authority:test-index-readiness",
        )
    )
    reader = MongoReadingEvidenceReadModelReader(
        database=database,
        configured_target=target,
        configuration=configuration,
        generation_id=fixture.generation_id,
    )
    return MongoReadingEvidenceSourceActionizer(
        reader=reader,
        verifier=ReadingEvidenceReadModelVerifier(),
    ).action(
        request=fixture.source_request(provider_source_id=reader.source_id)
    )


def _pipeline_request(
    *,
    fixture: ReadingEvidenceStorageFixture,
    configuration: MongoReadingEvidenceConfiguration,
    target: ReadingEvidenceMaterializationTarget,
) -> ReadingEvidenceProjectionPipelineRequest:
    return ReadingEvidenceProjectionPipelineRequest.create(
        source=ReadingEvidenceStorageProjectionSource(result=fixture.canonical),
        target=target,
        configuration=ReadingEvidenceProjectionPipelineConfiguration.create(
            projection_configuration=(
                ReadingEvidenceStorageProjectionConfiguration.v1(
                    generation_id=fixture.generation_id
                )
            ),
            materialization_configuration=configuration.materialization,
        ),
        authority_id="authority:test-reading-evidence-write",
    )


def test__pipeline__projects_materializes_and_exactly_replays() -> None:
    fixture = ReadingEvidenceStorageFixture.visual()
    configuration = MongoReadingEvidenceConfiguration.v1()
    database = cast(
        Database[MongoDocument],
        mongomock.MongoClient()["reading_evidence_pipeline_test"],
    )
    target = _target(
        database=database,
        configuration=configuration,
        deployment_id="pipeline-primary",
    )
    materializer = MongoReadingEvidenceMaterializer(
        database=database,
        configured_target=target,
        configuration=configuration,
    )
    pipeline = ReadingEvidenceProjectionMaterializationPipeline(
        materializer=materializer
    )
    request = _pipeline_request(
        fixture=fixture,
        configuration=configuration,
        target=target,
    )

    first = pipeline.action(request=request)
    observed = _source_result(
        database=database,
        configuration=configuration,
        target=target,
        fixture=fixture,
    )
    replay = pipeline.action(request=request)
    replay_verification = ReadingEvidenceEquivalenceVerifier().action(
        request=ReadingEvidenceEquivalenceRequest(
            kind=ReadingEvidenceEquivalenceKind.SAME_STORE_REPLAY,
            reference=observed,
            observed=observed,
            reference_materialization=first.evidence,
            replay_materialization=replay.evidence,
        )
    )

    assert isinstance(pipeline, Pipeline)
    assert first.request_id == request.request_id
    assert (
        sum(value.created_count for value in first.evidence.collections)
        == first.evidence.projected_document_count
    )
    assert (
        sum(value.unchanged_count for value in replay.evidence.collections)
        == replay.evidence.projected_document_count
    )
    assert replay_verification.equivalent
    assert pipeline.identity.stage_actionizer_ids == (
        ReadingEvidenceStorageProjector.identity.projector_id,
        materializer.identity.materializer_id,
    )


def test__pipeline__supports_independent_rebuild_equivalence() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    configuration = MongoReadingEvidenceConfiguration.v1()
    primary = cast(
        Database[MongoDocument],
        mongomock.MongoClient()["reading_evidence_primary_test"],
    )
    rebuild = cast(
        Database[MongoDocument],
        mongomock.MongoClient()["reading_evidence_rebuild_test"],
    )
    primary_target = _target(
        database=primary,
        configuration=configuration,
        deployment_id="pipeline-primary",
    )
    rebuild_target = _target(
        database=rebuild,
        configuration=configuration,
        deployment_id="pipeline-independent-rebuild",
    )

    for database, target in (
        (primary, primary_target),
        (rebuild, rebuild_target),
    ):
        ReadingEvidenceProjectionMaterializationPipeline(
            materializer=MongoReadingEvidenceMaterializer(
                database=database,
                configured_target=target,
                configuration=configuration,
            )
        ).action(
            request=_pipeline_request(
                fixture=fixture,
                configuration=configuration,
                target=target,
            )
        )

    reference = _source_result(
        database=primary,
        configuration=configuration,
        target=primary_target,
        fixture=fixture,
    )
    observed = _source_result(
        database=rebuild,
        configuration=configuration,
        target=rebuild_target,
        fixture=fixture,
    )
    result = ReadingEvidenceEquivalenceVerifier().action(
        request=ReadingEvidenceEquivalenceRequest(
            kind=ReadingEvidenceEquivalenceKind.INDEPENDENT_REBUILD,
            reference=reference,
            observed=observed,
            reference_materialization=None,
            replay_materialization=None,
        )
    )

    assert result.equivalent

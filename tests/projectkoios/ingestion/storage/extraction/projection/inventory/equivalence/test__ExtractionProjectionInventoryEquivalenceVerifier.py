from __future__ import annotations

import pytest
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.materialization.collection_evidence import (  # noqa: E501
    ExtractionProjectionMaterializationCollectionEvidence,
)
from projectkoios.ingestion.storage.extraction.materialization.configuration import (  # noqa: E501
    ExtractionProjectionMaterializationConfiguration,
)
from projectkoios.ingestion.storage.extraction.materialization.evidence import (
    ExtractionProjectionMaterializationEvidence,
)
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.collection import (
    ExtractionProjectionCollection,
)
from projectkoios.ingestion.storage.extraction.projection.configuration import (
    ExtractionProjectionConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.document import (
    ExtractionProjectionDocument,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.configuration import (  # noqa: E501
    ExtractionProjectionInventoryConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.kind import (  # noqa: E501
    ExtractionProjectionEquivalenceKind,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.mismatch import (  # noqa: E501
    ExtractionProjectionInventoryMismatch,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.request import (  # noqa: E501
    ExtractionProjectionInventoryEquivalenceRequest,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.verifier import (  # noqa: E501
    ExtractionProjectionInventoryEquivalenceVerifier,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.evidence import (  # noqa: E501
    ExtractionProjectionInventoryEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.expected import (  # noqa: E501
    ExpectedExtractionProjectionInventory,
)
from projectkoios.ingestion.storage.extraction.projection.read_model import (
    ExtractionReadModel,
)


def _target(
    deployment_id: str = "fixture-mongodb",
) -> ExtractionProjectionTargetIdentity:
    return ExtractionProjectionTargetIdentity.create(
        deployment_id=deployment_id,
        environment="test",
        database_name="fixture_database",
        schema_id="extraction-read-model-v1",
        projection_slot="extraction-publications",
    )


def _read_model(text: str = "exact") -> ExtractionReadModel:
    projection_configuration = ExtractionProjectionConfiguration.v1()
    document = ExtractionProjectionDocument.create(
        collection=ExtractionProjectionCollection.BLOCKS,
        value={
            "_id": "block:fixture",
            "publication_digest": "a" * 64,
            "text": text,
        },
    )
    return ExtractionReadModel.create(
        source_evidence_ids=("evidence:fixture",),
        configuration_id=projection_configuration.configuration_id,
        schema_id=projection_configuration.schema_id,
        documents=(document,),
    )


def _expected(
    text: str = "exact",
) -> ExpectedExtractionProjectionInventory:
    return ExpectedExtractionProjectionInventory.from_read_models(
        read_models=(_read_model(text),),
        target=_target(),
        configuration=ExtractionProjectionInventoryConfiguration.mongodb_v1(),
    )


def _observed(
    expected: ExpectedExtractionProjectionInventory,
) -> ExtractionProjectionInventoryEvidence:
    return ExtractionProjectionInventoryEvidence.create(
        target_id=expected.target_id,
        configuration_id=expected.configuration_id,
        authority_id="authority:inventory-query",
        schema_id=expected.schema_id,
        collections=expected.collections,
    )


def _replay_evidence(
    expected: ExpectedExtractionProjectionInventory,
) -> ExtractionProjectionMaterializationEvidence:
    inventory_configuration = (
        ExtractionProjectionInventoryConfiguration.mongodb_v1()
    )
    counts = {
        collection: next(
            item.document_count
            for item in expected.collections
            if item.collection_name
            == inventory_configuration.collection_name(collection)
        )
        for collection in ExtractionProjectionCollection
    }
    collections = tuple(
        ExtractionProjectionMaterializationCollectionEvidence.create(
            collection=collection,
            created_document_count=0,
            unchanged_document_count=counts[collection],
        )
        for collection in ExtractionProjectionCollection
    )
    return ExtractionProjectionMaterializationEvidence.create(
        projection_id="projection:replay-fixture",
        target_id=expected.target_id,
        configuration_id=(
            ExtractionProjectionMaterializationConfiguration.mongodb_v1().configuration_id
        ),
        authority_id="authority:replay-write",
        projected_document_count=sum(counts.values()),
        collections=collections,
    )


def test__equivalence_verifier__accepts_independent_rebuild_content() -> None:
    expected = _expected()
    request = ExtractionProjectionInventoryEquivalenceRequest.create(
        kind=ExtractionProjectionEquivalenceKind.INDEPENDENT_REBUILD,
        expected=expected,
        observed=_observed(expected),
    )

    result = ExtractionProjectionInventoryEquivalenceVerifier().action(
        request=request
    )

    assert result.equivalent is True
    assert result.disposition is ExtractionActionDisposition.CONTINUE
    assert result.mismatches == ()


def test__equivalence_verifier__detects_stored_content_difference() -> None:
    expected = _expected()
    changed = _expected("changed")
    request = ExtractionProjectionInventoryEquivalenceRequest.create(
        kind=ExtractionProjectionEquivalenceKind.INDEPENDENT_REBUILD,
        expected=expected,
        observed=_observed(changed),
    )

    result = ExtractionProjectionInventoryEquivalenceVerifier().action(
        request=request
    )

    assert result.equivalent is False
    assert result.disposition is (
        ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
    )
    assert result.mismatches == (
        ExtractionProjectionInventoryMismatch.COLLECTION_CONTENT,
    )
    assert result.mismatched_collection_names == ("extraction_blocks",)


def test__same_store_request__requires_replay_materialization_evidence() -> (
    None
):
    initial = _observed(_expected())
    expected = ExpectedExtractionProjectionInventory.from_observed(initial)

    with pytest.raises(TypeError, match="replay evidence is required"):
        ExtractionProjectionInventoryEquivalenceRequest.create(
            kind=ExtractionProjectionEquivalenceKind.SAME_STORE_REPLAY,
            expected=expected,
            observed=initial,
        )


def test__same_store_expectation__ignores_query_authority_identity() -> None:
    initial = _observed(_expected())
    expected = ExpectedExtractionProjectionInventory.from_observed(initial)
    replay_observed = ExtractionProjectionInventoryEvidence.create(
        target_id=initial.target_id,
        configuration_id=initial.configuration_id,
        authority_id="authority:renewed-query",
        schema_id=initial.schema_id,
        collections=initial.collections,
    )
    request = ExtractionProjectionInventoryEquivalenceRequest.create(
        kind=ExtractionProjectionEquivalenceKind.SAME_STORE_REPLAY,
        expected=expected,
        observed=replay_observed,
        replay_materialization=_replay_evidence(expected),
    )

    result = ExtractionProjectionInventoryEquivalenceVerifier().action(
        request=request
    )

    assert result.equivalent is True

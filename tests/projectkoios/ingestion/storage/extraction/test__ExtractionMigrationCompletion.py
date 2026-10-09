"""Extraction migration aggregate evidence and completion tests."""

from __future__ import annotations

import pytest
from projectkoios.ingestion.storage.extraction.journal.inventory import (
    ExtractionPublicationJournalInventory,
)
from projectkoios.ingestion.storage.extraction.journal.selection import (
    ExtractionPublicationSelectionInventory,
)
from projectkoios.ingestion.storage.extraction.materialization.configuration import (  # noqa: E501
    ExtractionProjectionMaterializationConfiguration,
)
from projectkoios.ingestion.storage.extraction.materialization.evidence.collection import (  # noqa: E501
    ExtractionProjectionMaterializationCollectionEvidence,
)
from projectkoios.ingestion.storage.extraction.materialization.evidence.inventory import (  # noqa: E501
    ExtractionProjectionMaterializationEvidenceInventory,
)
from projectkoios.ingestion.storage.extraction.materialization.evidence.model import (  # noqa: E501
    ExtractionProjectionMaterializationEvidence,
)
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.migration.completion.manifest import (  # noqa: E501
    ExtractionProjectionMigrationCompletionManifest,
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
from projectkoios.ingestion.storage.extraction.projection.read.model import (
    ExtractionReadModel,
)
from projectkoios.ingestion.storage.extraction.publication.record import (
    ExtractionPublicationRecord,
)


def _target(deployment: str) -> ExtractionProjectionTargetIdentity:
    return ExtractionProjectionTargetIdentity.create(
        deployment_id=deployment,
        environment="development",
        database_name="fixture",
        schema_id="extraction-read-model-v1",
        projection_slot="extraction-publications",
    )


def _read_model() -> ExtractionReadModel:
    configuration = ExtractionProjectionConfiguration.v1()
    return ExtractionReadModel.create(
        source_evidence_ids=("evidence:fixture",),
        configuration_id=configuration.configuration_id,
        schema_id=configuration.schema_id,
        documents=(
            ExtractionProjectionDocument.create(
                collection=ExtractionProjectionCollection.DOCUMENTS,
                value={
                    "_id": "document:fixture",
                    "publication_digest": "a" * 64,
                    "state": "complete",
                },
            ),
        ),
    )


def _observed(
    expected: ExpectedExtractionProjectionInventory,
) -> ExtractionProjectionInventoryEvidence:
    return ExtractionProjectionInventoryEvidence.create(
        target_id=expected.target_id,
        configuration_id=expected.configuration_id,
        authority_id="authority:inventory",
        schema_id=expected.schema_id,
        collections=expected.collections,
    )


def _replay(
    expected: ExpectedExtractionProjectionInventory,
) -> ExtractionProjectionMaterializationEvidenceInventory:
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
    evidence = ExtractionProjectionMaterializationEvidence.create(
        projection_id="projection:fixture",
        target_id=expected.target_id,
        configuration_id=(
            ExtractionProjectionMaterializationConfiguration.mongodb_v1().configuration_id
        ),
        authority_id="authority:materialization",
        projected_document_count=sum(counts.values()),
        collections=tuple(
            ExtractionProjectionMaterializationCollectionEvidence.create(
                collection=collection,
                created_document_count=0,
                unchanged_document_count=counts[collection],
            )
            for collection in ExtractionProjectionCollection
        ),
    )
    return ExtractionProjectionMaterializationEvidenceInventory(evidence)


def _record() -> ExtractionPublicationRecord:
    return ExtractionPublicationRecord.create(
        sequence=1,
        request_id="request:fixture",
        document_id="document:fixture",
        manifest_id="manifest:fixture",
        payload_sha256="a" * 64,
        payload_byte_size=100,
        previous_record_sha256=None,
    )


def _journal() -> ExtractionPublicationJournalInventory:
    return ExtractionPublicationJournalInventory(_record())


def _completion_evidence() -> dict[str, object]:
    inventory_configuration = (
        ExtractionProjectionInventoryConfiguration.mongodb_v1()
    )
    primary_expected = ExpectedExtractionProjectionInventory.from_read_models(
        read_models=(_read_model(),),
        target=_target("primary"),
        configuration=inventory_configuration,
    )
    primary_observed = _observed(primary_expected)
    replay = _replay(primary_expected)
    same_request = ExtractionProjectionInventoryEquivalenceRequest.create(
        kind=ExtractionProjectionEquivalenceKind.SAME_STORE_REPLAY,
        expected=primary_expected,
        observed=primary_observed,
        replay_materialization=replay,
        replay_materialization_configuration=(
            ExtractionProjectionMaterializationConfiguration.mongodb_v1()
        ),
    )
    same_result = ExtractionProjectionInventoryEquivalenceVerifier().action(
        request=same_request
    )
    independent_expected = (
        ExpectedExtractionProjectionInventory.for_target_from_observed(
            observed=primary_observed,
            target=_target("independent"),
        )
    )
    independent_observed = _observed(independent_expected)
    independent_request = (
        ExtractionProjectionInventoryEquivalenceRequest.create(
            kind=ExtractionProjectionEquivalenceKind.INDEPENDENT_REBUILD,
            expected=independent_expected,
            observed=independent_observed,
        )
    )
    independent_result = (
        ExtractionProjectionInventoryEquivalenceVerifier().action(
            request=independent_request
        )
    )
    record = _record()
    journal = ExtractionPublicationJournalInventory(record)
    selection = ExtractionPublicationSelectionInventory(
        journal_records=(record,),
        selected_request_ids=(record.request_id,),
    )
    return {
        "phase": "development-class-a",
        "migration_plan_sha256": "b" * 64,
        "source_repository_commit": "c" * 40,
        "eligible_identity_sha256": "d" * 64,
        "eligible_publication_request_sha256": selection.request_ids_sha256,
        "eligible_projection_ids_sha256": replay.projection_ids_sha256,
        "eligible_publication_count": 1,
        "selected_publications": selection,
        "source_journal_frozen": journal,
        "source_journal_rechecked": journal,
        "primary_expected": primary_expected,
        "primary_observed": primary_observed,
        "replay_materialization": replay,
        "same_store_equivalence": same_result,
        "independent_expected": independent_expected,
        "independent_observed": independent_observed,
        "independent_equivalence": independent_result,
    }


def test__migration_completion__binds_all_required_evidence() -> None:
    evidence = _completion_evidence()

    manifest = ExtractionProjectionMigrationCompletionManifest(**evidence)

    assert manifest.manifest_id
    assert manifest.source_journal_record_count == 1
    assert manifest.primary_observed_inventory_id
    assert manifest.replay_materialization_inventory_id
    assert manifest.independent_observed_inventory_id


def test__migration_completion__rejects_selected_publication_drift() -> None:
    evidence = _completion_evidence()
    evidence["eligible_publication_request_sha256"] = "f" * 64

    with pytest.raises(ValueError, match="selected publications"):
        ExtractionProjectionMigrationCompletionManifest(**evidence)


def test__migration_completion__rejects_selection_from_another_journal() -> (
    None
):
    evidence = _completion_evidence()
    forged = ExtractionPublicationRecord.create(
        sequence=1,
        request_id="request:fixture",
        document_id="document:forged",
        manifest_id="manifest:forged",
        payload_sha256="f" * 64,
        payload_byte_size=100,
        previous_record_sha256=None,
    )
    evidence["selected_publications"] = ExtractionPublicationSelectionInventory(
        journal_records=(forged,),
        selected_request_ids=(forged.request_id,),
    )

    with pytest.raises(ValueError, match="frozen journal"):
        ExtractionProjectionMigrationCompletionManifest(**evidence)


def test__migration_completion__rejects_substituted_projection() -> None:
    evidence = _completion_evidence()
    replay = evidence["replay_materialization"]
    assert isinstance(
        replay, ExtractionProjectionMaterializationEvidenceInventory
    )
    original = next(iter(replay))
    substituted = ExtractionProjectionMaterializationEvidence.create(
        projection_id="projection:substituted",
        target_id=original.target_id,
        configuration_id=original.configuration_id,
        authority_id=original.authority_id,
        projected_document_count=original.projected_document_count,
        collections=original.collections,
    )
    evidence["replay_materialization"] = (
        ExtractionProjectionMaterializationEvidenceInventory(substituted)
    )

    with pytest.raises(ValueError, match="projection set differs"):
        ExtractionProjectionMigrationCompletionManifest(**evidence)


def test__migration_completion__rejects_source_journal_drift() -> None:
    evidence = _completion_evidence()
    first = _journal()
    record_one = ExtractionPublicationRecord.create(
        sequence=1,
        request_id="request:fixture",
        document_id="document:fixture",
        manifest_id="manifest:fixture",
        payload_sha256="a" * 64,
        payload_byte_size=100,
        previous_record_sha256=None,
    )
    record_two = ExtractionPublicationRecord.create(
        sequence=2,
        request_id="request:second",
        document_id="document:second",
        manifest_id="manifest:second",
        payload_sha256="e" * 64,
        payload_byte_size=200,
        previous_record_sha256=record_one.record_sha256,
    )
    evidence["source_journal_frozen"] = first
    evidence["source_journal_rechecked"] = (
        ExtractionPublicationJournalInventory(record_one, record_two)
    )

    with pytest.raises(ValueError, match="drifted"):
        ExtractionProjectionMigrationCompletionManifest(**evidence)


def test__materialization_inventory__rejects_duplicate_projection() -> None:
    evidence = _completion_evidence()
    replay = evidence["replay_materialization"]
    assert isinstance(
        replay, ExtractionProjectionMaterializationEvidenceInventory
    )
    item = next(iter(replay))

    with pytest.raises(ValueError, match="unique"):
        ExtractionProjectionMaterializationEvidenceInventory(item, item)

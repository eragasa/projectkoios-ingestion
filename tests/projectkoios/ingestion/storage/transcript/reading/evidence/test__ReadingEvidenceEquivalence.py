"""Backend-neutral reading-evidence equivalence tests."""

from __future__ import annotations

import pytest
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.kind import (  # noqa: E501
    ReadingEvidenceEquivalenceKind,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.mismatch import (  # noqa: E501
    ReadingEvidenceEquivalenceMismatch,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.request import (  # noqa: E501
    ReadingEvidenceEquivalenceRequest,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.verifier import (  # noqa: E501
    ReadingEvidenceEquivalenceVerifier,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.evidence import (  # noqa: E501
    ReadingEvidenceMaterializationCollectionEvidence,
    ReadingEvidenceMaterializationCollectionEvidenceInventory,
    ReadingEvidenceMaterializationEvidence,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.collection import (  # noqa: E501
    ReadingEvidenceStorageCollection,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.source.verifier import (  # noqa: E501
    ReadingEvidenceReadModelVerifier,
)
from projectkoios.ingestion.transcript.reading.evidence.source.result import (
    ReadingEvidenceSourceResult,
)

from tests.projectkoios.ingestion.storage.transcript.reading.evidence.fixture import (  # noqa: E501
    ReadingEvidenceStorageFixture,
)


def _source(
    fixture: ReadingEvidenceStorageFixture,
    provider: str,
) -> ReadingEvidenceSourceResult:
    return ReadingEvidenceReadModelVerifier().verify(
        request=fixture.source_request(provider_source_id=provider),
        read_model=fixture.read_model,
        provider_implementation_id=provider,
    )


def _materialization(
    fixture: ReadingEvidenceStorageFixture,
    *,
    replay: bool,
) -> ReadingEvidenceMaterializationEvidence:
    counts = {
        collection: sum(
            document.kind.collection is collection
            for document in fixture.read_model.documents
        )
        for collection in ReadingEvidenceStorageCollection
    }
    collections = ReadingEvidenceMaterializationCollectionEvidenceInventory(
        *(
            ReadingEvidenceMaterializationCollectionEvidence(
                collection=collection,
                created_count=0 if replay else counts[collection],
                unchanged_count=counts[collection] if replay else 0,
            )
            for collection in ReadingEvidenceStorageCollection
        )
    )
    return ReadingEvidenceMaterializationEvidence(
        projection_id=fixture.read_model.projection_id,
        target_id="unit-test-target",
        configuration_id="unit-test-configuration",
        authority_id="unit-test-authority",
        projected_document_count=len(fixture.read_model.documents),
        collections=collections,
    )


def test__equivalence__accepts_independent_exact_reconstruction() -> None:
    fixture = ReadingEvidenceStorageFixture.visual()
    request = ReadingEvidenceEquivalenceRequest(
        kind=ReadingEvidenceEquivalenceKind.INDEPENDENT_REBUILD,
        reference=_source(fixture, "disk-reader:1.0"),
        observed=_source(fixture, "mongodb-reader:1.0"),
        reference_materialization=None,
        replay_materialization=None,
    )

    result = ReadingEvidenceEquivalenceVerifier().action(request=request)

    assert result.equivalent
    assert len(result.mismatches) == 0


def test__equivalence__reports_distinct_canonical_sources() -> None:
    paragraph = ReadingEvidenceStorageFixture.paragraph()
    visual = ReadingEvidenceStorageFixture.visual()
    request = ReadingEvidenceEquivalenceRequest(
        kind=ReadingEvidenceEquivalenceKind.INDEPENDENT_REBUILD,
        reference=_source(paragraph, "disk-reader:1.0"),
        observed=_source(visual, "mongodb-reader:1.0"),
        reference_materialization=None,
        replay_materialization=None,
    )

    result = ReadingEvidenceEquivalenceVerifier().action(request=request)

    assert not result.equivalent
    assert tuple(result.mismatches) == (
        ReadingEvidenceEquivalenceMismatch.DOCUMENT,
        ReadingEvidenceEquivalenceMismatch.INVENTORY,
        ReadingEvidenceEquivalenceMismatch.PROJECTION_RESULT,
    )


def test__equivalence__requires_unchanged_same_store_replay() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    source = _source(fixture, "mongodb-reader:1.0")
    exact = ReadingEvidenceEquivalenceRequest(
        kind=ReadingEvidenceEquivalenceKind.SAME_STORE_REPLAY,
        reference=source,
        observed=source,
        reference_materialization=_materialization(fixture, replay=False),
        replay_materialization=_materialization(fixture, replay=True),
    )
    changed = ReadingEvidenceEquivalenceRequest(
        kind=ReadingEvidenceEquivalenceKind.SAME_STORE_REPLAY,
        reference=source,
        observed=source,
        reference_materialization=_materialization(fixture, replay=False),
        replay_materialization=_materialization(fixture, replay=False),
    )

    assert ReadingEvidenceEquivalenceVerifier().action(request=exact).equivalent
    result = ReadingEvidenceEquivalenceVerifier().action(request=changed)
    assert tuple(result.mismatches) == (
        ReadingEvidenceEquivalenceMismatch.REPLAY_OUTCOME,
    )


def test__equivalence__rejects_shifted_per_collection_replay_counts() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    source = _source(fixture, "mongodb-reader:1.0")
    baseline = _materialization(fixture, replay=False)
    exact_replay = _materialization(fixture, replay=True)
    shifted = ReadingEvidenceMaterializationCollectionEvidenceInventory(
        *(
            ReadingEvidenceMaterializationCollectionEvidence(
                collection=value.collection,
                created_count=0,
                unchanged_count=(
                    value.unchanged_count - 1
                    if value.collection
                    is ReadingEvidenceStorageCollection.DOCUMENTS
                    else value.unchanged_count + 1
                    if value.collection
                    is ReadingEvidenceStorageCollection.PAGES
                    else value.unchanged_count
                ),
            )
            for value in exact_replay.collections
        )
    )
    replay = ReadingEvidenceMaterializationEvidence(
        projection_id=exact_replay.projection_id,
        target_id=exact_replay.target_id,
        configuration_id=exact_replay.configuration_id,
        authority_id=exact_replay.authority_id,
        projected_document_count=exact_replay.projected_document_count,
        collections=shifted,
    )
    request = ReadingEvidenceEquivalenceRequest(
        kind=ReadingEvidenceEquivalenceKind.SAME_STORE_REPLAY,
        reference=source,
        observed=source,
        reference_materialization=baseline,
        replay_materialization=replay,
    )

    result = ReadingEvidenceEquivalenceVerifier().action(request=request)

    assert tuple(result.mismatches) == (
        ReadingEvidenceEquivalenceMismatch.REPLAY_OUTCOME,
    )


def test__equivalence__separates_replay_from_independent_rebuild() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    source = _source(fixture, "mongodb-reader:1.0")

    with pytest.raises(ValueError, match="cannot bind materialization"):
        ReadingEvidenceEquivalenceRequest(
            kind=ReadingEvidenceEquivalenceKind.INDEPENDENT_REBUILD,
            reference=source,
            observed=source,
            reference_materialization=_materialization(fixture, replay=False),
            replay_materialization=_materialization(fixture, replay=True),
        )

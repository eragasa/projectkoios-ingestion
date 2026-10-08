"""Current-schema backend-neutral reading-evidence storage tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest
from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.storage.transcript.reading.evidence.completion.collection import (  # noqa: E501
    ReadingEvidenceStorageCollectionDigestInventory,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.completion.manifest import (  # noqa: E501
    ReadingEvidenceCompletionManifest,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.json.contract import (  # noqa: E501
    ReadingEvidenceStorageJsonContract,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.kind import (  # noqa: E501
    ReadingEvidenceStorageRecordKind,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.record.codec import (  # noqa: E501
    ReadingEvidenceStorageRecordCodec,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.source.verifier import (  # noqa: E501
    ReadingEvidenceReadModelVerifier,
)

from tests.projectkoios.ingestion.storage.transcript.reading.evidence.fixture import (  # noqa: E501
    ReadingEvidenceStorageFixture,
)


def test__storage_projection__is_deterministic_and_completed() -> None:
    first = ReadingEvidenceStorageFixture.paragraph()
    second = ReadingEvidenceStorageFixture.paragraph()

    assert first.read_model == second.read_model
    completions = first.read_model.documents.for_kind(
        ReadingEvidenceStorageRecordKind.COMPLETION
    )
    assert len(completions) == 1
    manifest = ReadingEvidenceStorageJsonContract().decode_as(
        completions[0].payload(), ReadingEvidenceCompletionManifest
    )
    children = type(first.read_model.documents)(
        *(
            document
            for document in first.read_model.documents
            if document.kind is not ReadingEvidenceStorageRecordKind.COMPLETION
        )
    )
    assert manifest.collections == (
        ReadingEvidenceStorageCollectionDigestInventory.observe(children)
    )
    assert manifest.storage_configuration_id == (
        first.read_model.configuration_id
    )


def test__read_model_verifier__round_trips_paragraph_and_visual_evidence() -> (
    None
):
    verifier = ReadingEvidenceReadModelVerifier()

    for fixture in (
        ReadingEvidenceStorageFixture.paragraph(),
        ReadingEvidenceStorageFixture.visual(),
    ):
        result = verifier.verify(
            request=fixture.source_request(),
            read_model=fixture.read_model,
            provider_implementation_id="unit-test-reader:1.0",
        )

        assert result.document == fixture.canonical.document
        assert result.inventory == fixture.canonical.inventory
        assert result.projection_result_id == fixture.canonical.result_id


def test__read_model_verifier__enforces_canonical_domain_bounds() -> None:
    fixture = ReadingEvidenceStorageFixture.visual()
    request = replace(
        fixture.source_request(),
        maximum_artifact_count=1,
    )

    with pytest.raises(ValueError, match="exceeds request bound"):
        ReadingEvidenceReadModelVerifier().verify(
            request=request,
            read_model=fixture.read_model,
            provider_implementation_id="unit-test-reader:1.0",
        )


def test__record_codec__round_trips_only_complete_child_graph() -> None:
    fixture = ReadingEvidenceStorageFixture.visual()
    children = type(fixture.read_model.documents)(
        *(
            document
            for document in fixture.read_model.documents
            if document.kind is not ReadingEvidenceStorageRecordKind.COMPLETION
        )
    )

    reconstructed = ReadingEvidenceStorageRecordCodec().decode_children(
        children
    )

    assert reconstructed == fixture.canonical.document


def test__json_contract__rejects_changed_derived_identity() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    reference = next(iter(fixture.canonical.document.managed_artifacts))
    contract = ReadingEvidenceStorageJsonContract()
    value = contract.to_json_value(reference)
    assert type(value) is dict
    tampered = deepcopy(value)
    derived = tampered["derived"]
    assert type(derived) is dict
    derived["artifact_id"] = "managed-artifact:sha256:" + "0" * 64

    with pytest.raises(JsonParseError, match="stored derived field differs"):
        contract.from_json_value(tampered)


def test__json_contract__rejects_noncanonical_and_duplicate_json() -> None:
    fixture = ReadingEvidenceStorageFixture.paragraph()
    reference = next(iter(fixture.canonical.document.managed_artifacts))
    contract = ReadingEvidenceStorageJsonContract()
    canonical = contract.serialize_text(reference)

    with pytest.raises(JsonParseError, match="not canonical"):
        contract.parse_text(canonical.replace(":", ": ", 1))
    with pytest.raises(JsonParseError, match="duplicate"):
        contract.parse_text('{"$type":"x","$type":"y"}')

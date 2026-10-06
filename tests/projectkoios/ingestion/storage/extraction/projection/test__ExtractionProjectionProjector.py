from __future__ import annotations

import json

import pytest
from projectkoios.ingestion.base.projector.identity_error import (
    ProjectionIdentityError,
)
from projectkoios.ingestion.base.projector.payload_error import (
    ProjectionPayloadError,
)
from projectkoios.ingestion.base.projector.request import ProjectionRequest
from projectkoios.ingestion.identity import canonical_json
from projectkoios.ingestion.models import ExtractionResult
from projectkoios.ingestion.serialization import serialize_contract
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.storage.extraction.projection.collection import (
    ExtractionProjectionCollection,
)
from projectkoios.ingestion.storage.extraction.projection.configuration import (
    ExtractionProjectionConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.evidence import (
    ExtractionPublicationEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.projector import (
    ExtractionProjectionProjector,
)
from projectkoios.ingestion.storage.extraction.publication.record import (
    ExtractionPublicationRecord,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)


def _evidence(
    extraction: ExtractionResult,
    *,
    sequence: int = 1,
    previous: str | None = None,
    payload: bytes | None = None,
    record_document_id: str | None = None,
) -> ExtractionPublicationEvidence:
    exact_payload = payload or serialize_contract(extraction).encode("utf-8")
    request = ExtractionPublicationRequest.create(extraction=extraction)
    record = ExtractionPublicationRecord.create(
        sequence=sequence,
        request_id=request.request_id,
        document_id=record_document_id or extraction.document.document_id,
        manifest_id=extraction.manifest.manifest_id,
        payload_sha256=SHA256Fingerprinter.fingerprint(content=exact_payload),
        payload_byte_size=len(exact_payload),
        previous_record_sha256=previous,
    )
    return ExtractionPublicationEvidence.create(
        record=record,
        payload=exact_payload,
    )


def _request(
    *evidence: ExtractionPublicationEvidence,
) -> ProjectionRequest[
    ExtractionPublicationEvidence,
    ExtractionProjectionConfiguration,
]:
    return ProjectionRequest.create(
        sources=tuple(sorted(evidence, key=lambda item: item.evidence_id)),
        configuration=ExtractionProjectionConfiguration.v1(),
    )


def test__extraction_projection_projector__is_deterministic_and_complete(
    extraction_result: ExtractionResult,
) -> None:
    evidence = _evidence(extraction_result)
    projector = ExtractionProjectionProjector()
    request = _request(evidence)

    first = projector.action(request=request)
    second = projector.action(request=request)

    assert first == second
    assert first.projection.configuration_id == (
        request.configuration.configuration_id
    )
    assert first.projection.schema_id == "extraction-read-model-v1"
    assert tuple(
        document.collection for document in first.projection.documents
    ) == (
        ExtractionProjectionCollection.BLOCKS,
        ExtractionProjectionCollection.DOCUMENTS,
        ExtractionProjectionCollection.MANIFESTS,
        ExtractionProjectionCollection.PAGES,
    )
    assert all(
        json.loads(document.document_json)["projection_content_sha256"]
        == document.content_sha256
        for document in first.projection.documents
    )
    root = next(
        document
        for document in first.projection.documents
        if document.collection is ExtractionProjectionCollection.DOCUMENTS
    )
    assert json.loads(root.document_json)["publication_state"] == "complete"


def test__extraction_projection_projector__rejects_noncanonical_payload(
    extraction_result: ExtractionResult,
) -> None:
    value = json.loads(serialize_contract(extraction_result))
    noncanonical = json.dumps(value, indent=2).encode("utf-8")
    evidence = _evidence(extraction_result, payload=noncanonical)

    with pytest.raises(ProjectionPayloadError, match="not canonical JSON"):
        ExtractionProjectionProjector().action(request=_request(evidence))


def test__extraction_projection_projector__classifies_structural_payload_error(
    extraction_result: ExtractionResult,
) -> None:
    value = json.loads(serialize_contract(extraction_result))
    del value["document"]["pages"][0]["blocks"]
    payload = canonical_json(value).encode("utf-8")
    evidence = _evidence(extraction_result, payload=payload)

    with pytest.raises(
        ProjectionPayloadError,
        match="page blocks are invalid",
    ):
        ExtractionProjectionProjector().action(request=_request(evidence))


def test__extraction_projection_projector__separates_identity_disagreement(
    extraction_result: ExtractionResult,
) -> None:
    value = json.loads(serialize_contract(extraction_result))
    value["document"]["document_id"] = "document:sha256:" + ("0" * 64)
    payload = canonical_json(value).encode("utf-8")
    evidence = _evidence(extraction_result, payload=payload)

    with pytest.raises(
        ProjectionIdentityError,
        match="record and payload identities differ",
    ):
        ExtractionProjectionProjector().action(request=_request(evidence))


def test__extraction_projection_projector__rejects_duplicate_output_identity(
    extraction_result: ExtractionResult,
) -> None:
    first = _evidence(extraction_result)
    second = _evidence(
        extraction_result,
        sequence=2,
        previous=first.record.record_sha256,
    )

    with pytest.raises(
        ProjectionIdentityError,
        match="identities are not unique",
    ):
        ExtractionProjectionProjector().action(request=_request(first, second))

from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.models import ExtractionResult
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.actions.status import (
    ExtractionActionStatus,
)
from projectkoios.ingestion.storage.extraction.artifact.validation.actionizer import (  # noqa: E501
    ExistingExtractionArtifactValidationActionizer,
)
from projectkoios.ingestion.storage.extraction.artifact.validation.reader.base import (  # noqa: E501
    ExtractionArtifactReader,
)
from projectkoios.ingestion.storage.extraction.artifact.validation.reader.error import (  # noqa: E501
    ExtractionArtifactReaderError,
)
from projectkoios.ingestion.storage.extraction.artifact.validation.request import (  # noqa: E501
    ExistingExtractionArtifactValidationRequest,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)


class MemoryReader(ExtractionArtifactReader):
    def __init__(
        self,
        content: bytes,
        error: ExtractionArtifactReaderError | None = None,
    ) -> None:
        self.content = content
        self.error = error

    def read(
        self,
        *,
        artifact_reference: str,
        authority_id: str,
        maximum_bytes: int,
    ) -> bytes:
        assert artifact_reference == "artifact:fixture"
        assert authority_id == "authority:fixture"
        assert len(self.content) <= maximum_bytes
        if self.error is not None:
            raise self.error
        return self.content


def request_for(
    extraction: ExtractionResult,
    content: bytes,
    *,
    document_id: str | None = None,
) -> ExistingExtractionArtifactValidationRequest:
    payload = CanonicalJsonSerializer.serialize_text(extraction).encode()
    publication = ExtractionPublicationRequest.create(extraction=extraction)
    return ExistingExtractionArtifactValidationRequest.create(
        artifact_reference="artifact:fixture",
        authority_id="authority:fixture",
        expected_artifact_sha256=SHA256Fingerprinter.fingerprint(
            content=content
        ),
        expected_artifact_byte_size=len(content),
        expected_source_sha256=extraction.document.source.content_hash,
        expected_document_id=document_id or extraction.document.document_id,
        expected_manifest_id=extraction.manifest.manifest_id,
        expected_payload_sha256=SHA256Fingerprinter.fingerprint(
            content=payload
        ),
        expected_payload_byte_size=len(payload),
        expected_publication_request_id=publication.request_id,
        expected_page_count=len(extraction.document.pages),
        expected_block_count=sum(
            len(page.blocks) for page in extraction.document.pages
        ),
        expected_warning_count=len(extraction.warnings),
    )


def test__artifact_validation_actionizer__returns_compact_exact_evidence(
    extraction_result: ExtractionResult,
) -> None:
    content = (
        CanonicalJsonSerializer.serialize_text(extraction_result) + "\n"
    ).encode()
    request = request_for(extraction_result, content)
    actionizer = ExistingExtractionArtifactValidationActionizer(
        reader=MemoryReader(content)
    )

    first = actionizer.action(request=request)
    second = actionizer.action(request=request)

    assert first == second
    assert first.status is ExtractionActionStatus.COMPLETED
    assert first.disposition is ExtractionActionDisposition.CONTINUE
    assert first.idempotency_key == request.idempotency_key
    assert first.document_id == extraction_result.document.document_id
    assert not hasattr(first, "extraction")


def test__artifact_validation_request__separates_request_and_idempotency(
    extraction_result: ExtractionResult,
) -> None:
    content = (
        CanonicalJsonSerializer.serialize_text(extraction_result) + "\n"
    ).encode()
    first = request_for(extraction_result, content)
    second = ExistingExtractionArtifactValidationRequest.create(
        artifact_reference="artifact:fixture-copy",
        authority_id="authority:fixture-copy",
        expected_artifact_sha256=first.expected_artifact_sha256,
        expected_artifact_byte_size=first.expected_artifact_byte_size,
        expected_source_sha256=first.expected_source_sha256,
        expected_document_id=first.expected_document_id,
        expected_manifest_id=first.expected_manifest_id,
        expected_payload_sha256=first.expected_payload_sha256,
        expected_payload_byte_size=first.expected_payload_byte_size,
        expected_publication_request_id=first.expected_publication_request_id,
        expected_page_count=first.expected_page_count,
        expected_block_count=first.expected_block_count,
        expected_warning_count=first.expected_warning_count,
    )

    assert first.request_id != second.request_id
    assert first.idempotency_key == second.idempotency_key
    with pytest.raises(ValueError, match="request ID is inconsistent"):
        replace(first, authority_id="authority:changed")


def test__artifact_validation_actionizer__stops_on_changed_bytes(
    extraction_result: ExtractionResult,
) -> None:
    content = (
        CanonicalJsonSerializer.serialize_text(extraction_result) + "\n"
    ).encode()
    request = request_for(extraction_result, content)
    actionizer = ExistingExtractionArtifactValidationActionizer(
        reader=MemoryReader(content + b"changed")
    )

    result = actionizer.action(request=request)

    assert result.status is ExtractionActionStatus.FAILED
    assert (
        result.disposition is ExtractionActionDisposition.STOP_INVALID_EVIDENCE
    )
    assert result.failure_code == "artifact_bytes_differ"


def test__artifact_validation_actionizer__stops_on_identity_ambiguity(
    extraction_result: ExtractionResult,
) -> None:
    content = (
        CanonicalJsonSerializer.serialize_text(extraction_result) + "\n"
    ).encode()
    request = request_for(
        extraction_result,
        content,
        document_id="document:sha256:" + "0" * 64,
    )
    actionizer = ExistingExtractionArtifactValidationActionizer(
        reader=MemoryReader(content)
    )

    result = actionizer.action(request=request)

    assert result.status is ExtractionActionStatus.FAILED
    assert (
        result.disposition
        is ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
    )
    assert result.failure_code == "extraction_identity_differs"


def test__artifact_validation_actionizer__stops_on_invalid_exact_artifact(
    extraction_result: ExtractionResult,
) -> None:
    content = b"not a serialized ExtractionResult"
    request = request_for(extraction_result, content)
    actionizer = ExistingExtractionArtifactValidationActionizer(
        reader=MemoryReader(content)
    )

    result = actionizer.action(request=request)

    assert result.status is ExtractionActionStatus.FAILED
    assert (
        result.disposition is ExtractionActionDisposition.STOP_INVALID_EVIDENCE
    )
    assert result.failure_code == "invalid_extraction_artifact"


def test__artifact_validation_actionizer__preserves_reader_disposition(
    extraction_result: ExtractionResult,
) -> None:
    content = (
        CanonicalJsonSerializer.serialize_text(extraction_result) + "\n"
    ).encode()
    request = request_for(extraction_result, content)
    error = ExtractionArtifactReaderError(
        code="artifact_temporarily_unavailable",
        disposition=ExtractionActionDisposition.RETRY_SAME_REQUEST,
        message="artifact is temporarily unavailable",
    )
    actionizer = ExistingExtractionArtifactValidationActionizer(
        reader=MemoryReader(content, error)
    )

    result = actionizer.action(request=request)

    assert result.status is ExtractionActionStatus.FAILED
    assert result.disposition is ExtractionActionDisposition.RETRY_SAME_REQUEST
    assert result.failure_code == "artifact_temporarily_unavailable"

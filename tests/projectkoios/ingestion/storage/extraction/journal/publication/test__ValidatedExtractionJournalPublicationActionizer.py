from __future__ import annotations

from pathlib import Path

from projectkoios.ingestion.integrations.disk.extraction.store import (
    DiskExtractionPublicationStore,
)
from projectkoios.ingestion.models import ExtractionResult
from projectkoios.ingestion.serialization import serialize_contract
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
from projectkoios.ingestion.storage.extraction.artifact.validation.request import (  # noqa: E501
    ExistingExtractionArtifactValidationRequest,
)
from projectkoios.ingestion.storage.extraction.journal.publication.actionizer import (  # noqa: E501
    ValidatedExtractionJournalPublicationActionizer,
)
from projectkoios.ingestion.storage.extraction.journal.publication.request import (  # noqa: E501
    ValidatedExtractionJournalPublicationRequest,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)


class MemoryReader(ExtractionArtifactReader):
    def __init__(self, content: bytes) -> None:
        self.content = content

    def read(
        self,
        *,
        artifact_reference: str,
        authority_id: str,
        maximum_bytes: int,
    ) -> bytes:
        assert artifact_reference == "artifact:fixture"
        assert authority_id == "authority:artifact-read"
        assert len(self.content) <= maximum_bytes
        return self.content


def validation_request(
    extraction: ExtractionResult,
    content: bytes,
) -> ExistingExtractionArtifactValidationRequest:
    payload = serialize_contract(extraction).encode()
    publication = ExtractionPublicationRequest.create(extraction=extraction)
    return ExistingExtractionArtifactValidationRequest.create(
        artifact_reference="artifact:fixture",
        authority_id="authority:artifact-read",
        expected_artifact_sha256=SHA256Fingerprinter.fingerprint(
            content=content
        ),
        expected_artifact_byte_size=len(content),
        expected_source_sha256=extraction.document.source.content_hash,
        expected_document_id=extraction.document.document_id,
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


def publication_request(
    extraction: ExtractionResult,
    content: bytes,
) -> ValidatedExtractionJournalPublicationRequest:
    validation = validation_request(extraction, content)
    validation_result = ExistingExtractionArtifactValidationActionizer(
        reader=MemoryReader(content)
    ).action(request=validation)
    return ValidatedExtractionJournalPublicationRequest.create(
        journal_reference="journal:development-fixture",
        authority_id="authority:journal-write",
        validation_request=validation,
        validation_result=validation_result,
    )


def test__validated_journal_publication__creates_then_replays_exact_record(
    tmp_path: Path,
    extraction_result: ExtractionResult,
) -> None:
    content = (serialize_contract(extraction_result) + "\n").encode()
    request = publication_request(extraction_result, content)
    store = DiskExtractionPublicationStore(
        tmp_path / "journal",
        journal_reference=request.journal_reference,
    )
    actionizer = ValidatedExtractionJournalPublicationActionizer(
        reader=MemoryReader(content),
        backend=store,
    )

    created = actionizer.action(request=request)
    replayed = actionizer.action(request=request)

    assert created.status is ExtractionActionStatus.COMPLETED
    assert created.disposition is ExtractionActionDisposition.CONTINUE
    assert created.publication is not None
    assert created.publication.replayed is False
    assert replayed.publication is not None
    assert replayed.publication.replayed is True
    assert created.record == replayed.record
    assert len(store.records()) == 1


def test__validated_journal_publication__stops_before_write_on_changed_bytes(
    tmp_path: Path,
    extraction_result: ExtractionResult,
) -> None:
    content = (serialize_contract(extraction_result) + "\n").encode()
    request = publication_request(extraction_result, content)
    store = DiskExtractionPublicationStore(
        tmp_path / "journal",
        journal_reference=request.journal_reference,
    )
    actionizer = ValidatedExtractionJournalPublicationActionizer(
        reader=MemoryReader(content + b"changed"),
        backend=store,
    )

    result = actionizer.action(request=request)

    assert result.status is ExtractionActionStatus.FAILED
    assert (
        result.disposition is ExtractionActionDisposition.STOP_INVALID_EVIDENCE
    )
    assert result.failure_code == "artifact_bytes_differ"
    assert store.records() == ()


def test__validated_journal_publication__stops_on_other_journal(
    tmp_path: Path,
    extraction_result: ExtractionResult,
) -> None:
    content = (serialize_contract(extraction_result) + "\n").encode()
    request = publication_request(extraction_result, content)
    store = DiskExtractionPublicationStore(
        tmp_path / "journal",
        journal_reference="journal:other",
    )

    result = ValidatedExtractionJournalPublicationActionizer(
        reader=MemoryReader(content),
        backend=store,
    ).action(request=request)

    assert result.status is ExtractionActionStatus.FAILED
    assert (
        result.disposition
        is ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
    )
    assert result.failure_code == "journal_reference_differs"
    assert store.records() == ()

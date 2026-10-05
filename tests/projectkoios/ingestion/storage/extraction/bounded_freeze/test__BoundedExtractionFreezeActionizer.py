from __future__ import annotations

import hashlib
from typing import BinaryIO

import pytest
from projectkoios.ingestion.cache_identity import build_extraction_cache_key
from projectkoios.ingestion.models import (
    CONTRACT_VERSION,
    ExtractedDocument,
    ExtractedPage,
    ExtractionResult,
    IngestionManifest,
    IngestionStatus,
    SourceDocument,
)
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.actions.status import (
    ExtractionActionStatus,
)
from projectkoios.ingestion.storage.extraction.artifact_validation.result import (  # noqa: E501
    ExistingExtractionArtifactValidationResult,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.actionizer import (  # noqa: E501
    BoundedExtractionFreezeActionizer,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.extractor import (
    FreezableSourceExtractor,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.request import (
    BoundedExtractionFreezeRequest,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.result import (
    BoundedExtractionFreezeResult,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.source import (
    ExtractionSourceMaterial,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.source_reader import (  # noqa: E501
    ExtractionSourceReader,
)
from projectkoios.ingestion.storage.extraction.bounded_freeze.store import (
    ExtractionFreezeStore,
)


class MemorySourceReader(ExtractionSourceReader):
    def __init__(self, material: ExtractionSourceMaterial) -> None:
        self.material = material
        self.calls = 0

    def read_source(
        self,
        *,
        source_reference: str,
        authority_id: str,
        maximum_bytes: int,
    ) -> ExtractionSourceMaterial:
        assert source_reference == "source:fixture-reference"
        assert authority_id == "authority:source-read"
        assert len(self.material.content) <= maximum_bytes
        self.calls += 1
        return self.material


class MemoryFreezeStore(ExtractionFreezeStore):
    def __init__(self) -> None:
        self.content: bytes | None = None

    def read_if_exists(
        self,
        *,
        artifact_reference: str,
        authority_id: str,
        maximum_bytes: int,
    ) -> bytes | None:
        assert artifact_reference == "artifact:frozen-fixture"
        assert authority_id == "authority:artifact-read"
        assert self.content is None or len(self.content) <= maximum_bytes
        return self.content

    def create_once(
        self,
        *,
        artifact_reference: str,
        authority_id: str,
        content: bytes,
        maximum_bytes: int,
    ) -> bool:
        assert artifact_reference == "artifact:frozen-fixture"
        assert authority_id == "authority:artifact-write"
        assert len(content) <= maximum_bytes
        if self.content is None:
            self.content = content
            return True
        assert self.content == content
        return False


class FixtureExtractor(FreezableSourceExtractor):
    name = "fixture-extractor"
    version = "1"

    def __init__(self) -> None:
        self.calls = 0

    @property
    def extraction_version(self) -> str:
        return self.version

    @property
    def configuration_digest(self) -> str:
        return "configuration:fixture"

    def cache_key(self, source: SourceDocument) -> str:
        return build_extraction_cache_key(
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            extractor_name=self.name,
            extractor_version=self.version,
            configuration_digest=self.configuration_digest,
            contract_version=CONTRACT_VERSION,
        )

    def extract(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractionResult:
        assert content.read() == SOURCE_BYTES
        self.calls += 1
        document = ExtractedDocument.create(
            source=source,
            pages=(
                ExtractedPage(
                    page_index=0,
                    width=100.0,
                    height=200.0,
                    blocks=(),
                ),
            ),
        )
        manifest = IngestionManifest.create(
            source=source,
            extractor_name=self.name,
            extractor_version=self.version,
            configuration_digest=self.configuration_digest,
            object_ids=(document.document_id,),
            warning_ids=(),
            status=IngestionStatus.COMPLETED,
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:01Z",
        )
        return ExtractionResult(document=document, manifest=manifest)


class InvalidFixtureExtractor(FixtureExtractor):
    def extract(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractionResult:
        raise ValueError("fixture extraction rejected source")


SOURCE_BYTES = b"%PDF bounded freeze fixture"
LOCATOR = "private/bounded-freeze-fixture.pdf"


def freeze_request(
    extractor: FixtureExtractor,
) -> BoundedExtractionFreezeRequest:
    source = SourceDocument.from_bytes(
        SOURCE_BYTES,
        source_id="source:bounded-freeze-fixture",
        media_type="application/pdf",
        locator=LOCATOR,
    )
    return BoundedExtractionFreezeRequest.create(
        source_reference="source:fixture-reference",
        source_authority_id="authority:source-read",
        artifact_reference="artifact:frozen-fixture",
        artifact_read_authority_id="authority:artifact-read",
        artifact_write_authority_id="authority:artifact-write",
        source_id=source.source_id,
        media_type=source.media_type,
        expected_source_sha256=source.content_hash,
        expected_source_byte_size=source.byte_length,
        expected_locator_sha256=hashlib.sha256(LOCATOR.encode()).hexdigest(),
        expected_page_count=1,
        extractor_name=extractor.name,
        expected_extractor_version=extractor.version,
        configuration_digest=extractor.configuration_digest,
        expected_cache_key=extractor.cache_key(source),
    )


def test__bounded_extraction_freeze__creates_once_then_reuses() -> None:
    extractor = FixtureExtractor()
    source_reader = MemorySourceReader(
        ExtractionSourceMaterial(content=SOURCE_BYTES, locator=LOCATOR)
    )
    store = MemoryFreezeStore()
    request = freeze_request(extractor)
    actionizer = BoundedExtractionFreezeActionizer(
        source_reader=source_reader,
        artifact_store=store,
        extractor=extractor,
    )

    created = actionizer.action(request=request)
    replayed = actionizer.action(request=request)

    assert created.status is ExtractionActionStatus.COMPLETED
    assert created.created is True
    assert replayed.created is False
    assert created.validation_request == replayed.validation_request
    assert created.validation_result == replayed.validation_result
    assert extractor.calls == 1
    assert source_reader.calls == 1


def test__bounded_extraction_freeze__maps_typed_extraction_failure() -> None:
    extractor = InvalidFixtureExtractor()
    actionizer = BoundedExtractionFreezeActionizer(
        source_reader=MemorySourceReader(
            ExtractionSourceMaterial(content=SOURCE_BYTES, locator=LOCATOR)
        ),
        artifact_store=MemoryFreezeStore(),
        extractor=extractor,
    )

    result = actionizer.action(request=freeze_request(extractor))

    assert result.status is ExtractionActionStatus.FAILED
    assert (
        result.disposition is ExtractionActionDisposition.STOP_INVALID_EVIDENCE
    )
    assert result.failure_code == "source_extraction_failed"


def test__completed_freeze__rejects_failed_nested_validation() -> None:
    extractor = FixtureExtractor()
    actionizer = BoundedExtractionFreezeActionizer(
        source_reader=MemorySourceReader(
            ExtractionSourceMaterial(content=SOURCE_BYTES, locator=LOCATOR)
        ),
        artifact_store=MemoryFreezeStore(),
        extractor=extractor,
    )
    request = freeze_request(extractor)
    completed = actionizer.action(request=request)
    assert completed.validation_request is not None
    failed_validation = ExistingExtractionArtifactValidationResult.failed(
        request=completed.validation_request,
        disposition=ExtractionActionDisposition.STOP_INVALID_EVIDENCE,
        failure_code="fixture_validation_failed",
        actionizer_name="fixture-validation",
        actionizer_version="1",
    )

    with pytest.raises(
        ValueError,
        match="completed bounded-extraction result is invalid",
    ):
        BoundedExtractionFreezeResult.completed(
            request=request,
            created=True,
            validation_request=completed.validation_request,
            validation_result=failed_validation,
            actionizer_name="fixture-freeze",
            actionizer_version="1",
        )


def test__bounded_extraction_freeze__stops_on_changed_frozen_artifact() -> None:
    extractor = FixtureExtractor()
    source_reader = MemorySourceReader(
        ExtractionSourceMaterial(content=SOURCE_BYTES, locator=LOCATOR)
    )
    store = MemoryFreezeStore()
    store.content = b"invalid frozen artifact"
    actionizer = BoundedExtractionFreezeActionizer(
        source_reader=source_reader,
        artifact_store=store,
        extractor=extractor,
    )

    result = actionizer.action(request=freeze_request(extractor))

    assert result.status is ExtractionActionStatus.FAILED
    assert (
        result.disposition is ExtractionActionDisposition.STOP_INVALID_EVIDENCE
    )
    assert result.failure_code == "frozen_extraction_artifact_invalid"
    assert extractor.calls == 0
    assert source_reader.calls == 0
